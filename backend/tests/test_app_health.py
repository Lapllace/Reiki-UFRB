"""Testes de aplicação, health e migrações."""

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.db.session import create_db_engine


def test_app_boots(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == 200


def test_health_ready(client: TestClient) -> None:
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_migrations_created_tables(test_database_url: str) -> None:
    """Integração PostgreSQL: PENDENTE até o acesso ao banco ser configurado.

    O SQL offline da migração está em migrations_offline_postgresql.sql,
    mas isso não substitui a execução real (`alembic upgrade head`).
    """
    engine = create_db_engine(test_database_url)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    expected = {"users", "auth_sessions", "locations", "weekly_cycles", "reiki_sessions", "alembic_version"}
    assert expected <= names
