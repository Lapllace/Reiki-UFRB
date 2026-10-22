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
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
import app.models  # noqa: F401  (registra os modelos)
from app.models.user import Role, User

POSTGRES_INTEGRATION_AVAILABLE = bool(os.environ.get("TEST_DATABASE_URL"))


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


@pytest.fixture
def test_database_url() -> Generator[str, None, None]:
    """Banco PostgreSQL real para testes de integração (PENDENTE).

    Só é ativado quando TEST_DATABASE_URL está definido. Caso contrário
    os testes que o usam são marcados como pendentes, não silenciados.
    """
    if not POSTGRES_INTEGRATION_AVAILABLE:
        pytest.skip(
            "Integração PostgreSQL pendente: configure TEST_DATABASE_URL "
            "(o SQL offline da migração está em migrations_offline_postgresql.sql)."
        )
    suffix = uuid.uuid4().hex[:8]
    base_url = os.environ["TEST_DATABASE_URL"]
    db_name = f"reiki_test_{suffix}"
    admin_engine: Engine = create_engine(base_url.rsplit("/", 1)[0] + "/postgres")
    from sqlalchemy import text

    with admin_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    yield base_url.rsplit("/", 1)[0] + f"/{db_name}"
    with admin_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text(f'DROP DATABASE "{db_name}"'))
    admin_engine.dispose()


def login(client: TestClient, email: str, password: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
