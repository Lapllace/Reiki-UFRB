"""Conftest: fixtures de aplicação e banco para testes.

Dois níveis:

1. Unitários/aplicação: SQLite em memória. Os modelos são compatíveis
   (Uuid genérico, String enums, DateTime tz). Serve para validar
   mapeamento, rotas, serialização e autenticação — NÃO valida migrações
   nem restrições específicas do PostgreSQL.
2. Integração com PostgreSQL real: marcada como pendente (skip) até o
   usuário configurar o acesso ao banco. O SQL offline da migração está
   em `migrations_offline_postgresql.sql` para inspeção.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
import app.models  # noqa: F401  (registra os modelos)
from app.models.user import Role, User

@pytest.fixture(scope="session")
def sqlite_engine() -> Generator[Engine, None, None]:
    """Engine SQLite em memória com uma única conexão compartilhada."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(sqlite_engine) -> Generator:
    TestingSession = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    session = TestingSession()
    yield session
    session.rollback()
    session.close()
    # Limpa as tabelas entre testes (SQLite em memória é compartilhado).
    with sqlite_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(delete(table))


@pytest.fixture
def db_autoflush(sqlite_engine) -> Generator:
    """Sessão com autoflush=False para validar operações que fazem flush explícito."""
    TestingSession = sessionmaker(
        bind=sqlite_engine, autoflush=False, expire_on_commit=False
    )
    session = TestingSession()
    yield session
    session.rollback()
    session.close()
    with sqlite_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(delete(table))


@pytest.fixture
def client(sqlite_engine) -> Generator[TestClient, None, None]:
    app = create_app()
    test_settings = Settings(cors_origins="http://localhost:3000")
    app.dependency_overrides[get_settings] = lambda: test_settings

    TestingSession = sessionmaker(bind=sqlite_engine, expire_on_commit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(role: Role = Role.PARTICIPANT, password: str = "senha-teste-123", **kwargs) -> User:
        counter["n"] += 1
        user = User(
            name=kwargs.pop("name", f"Usuário {counter['n']}"),
            email=kwargs.pop("email", f"user{counter['n']}@teste.local"),
            password_hash=hash_password(password),
            role=role,
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture(scope="session")
def test_database_url() -> Generator[str, None, None]:
    """Cria um banco PostgreSQL exclusivo e aplica a cadeia Alembic."""
    configured_url = os.environ.get("TEST_DATABASE_URL")
    if not configured_url:
        pytest.skip(
            "PostgreSQL pendente: TEST_DATABASE_URL não está configurada."
        )
    suffix = uuid.uuid4().hex[:8]
    db_name = f"reiki_test_{suffix}"
    base_url, _separator, _database = configured_url.rpartition("/")
    if not base_url or not _database:
        pytest.fail("TEST_DATABASE_URL deve incluir uma URL PostgreSQL com banco.")
    admin_engine: Engine | None = None
    temp_url = f"{base_url}/{db_name}"
    try:
        admin_engine = create_engine(f"{base_url}/postgres", poolclass=NullPool)
        with admin_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f'CREATE DATABASE "{db_name}"')
            )
        migration_env = os.environ.copy()
        migration_env["DATABASE_URL"] = temp_url
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=migration_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(
                "Não foi possível aplicar as migrações Alembic no banco temporário "
                f"(exit {result.returncode})."
            )
        yield temp_url
    except pytest.skip.Exception:
        raise
    except Exception as exc:
        pytest.fail(
            "Não foi possível preparar o PostgreSQL temporário; "
            f"verifique TEST_DATABASE_URL e permissões ({type(exc).__name__})."
        )
    finally:
        if admin_engine is not None:
            try:
                with admin_engine.connect() as conn:
                    conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :db AND pid <> pg_backend_pid()"
                        ),
                        {"db": db_name},
                    )
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
            finally:
                admin_engine.dispose()


@pytest.fixture
def postgres_engine(test_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(test_database_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session_factory(postgres_engine: Engine):
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    with postgres_engine.begin() as conn:
        # enrollments.reallocation_id → reallocation_cases.id usa ondelete=RESTRICT.
        # reallocation_cases.origin_enrollment_id → enrollments.id usa ondelete=CASCADE.
        # Esse ciclo impede o DELETE em cascata normal: o PostgreSQL rejeita apagar
        # reallocation_cases enquanto alguma enrollment ainda referencia o caso via
        # fk_enrollments_reallocation_id.
        # Anulamos reallocation_id antes da limpeza geral para quebrar o ciclo.
        # A FK permanece intacta — apenas os dados de teste são descartados.
        conn.execute(text("UPDATE enrollments SET reallocation_id = NULL WHERE reallocation_id IS NOT NULL"))
        for table in reversed(Base.metadata.sorted_tables):
            if table.name != "alembic_version":
                conn.execute(delete(table))
    return factory


@pytest.fixture
def postgres_db(postgres_session_factory) -> Generator[Session, None, None]:
    session = postgres_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def login(client: TestClient, email: str, password: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
