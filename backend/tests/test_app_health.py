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
    engine = create_db_engine(test_database_url)
    try:
        inspector = inspect(engine)
        names = set(inspector.get_table_names())
        expected = {
            "users", "auth_sessions", "locations", "weekly_cycles",
            "reiki_sessions", "weekly_availabilities", "availability_entries",
            "enrollments", "cover_requests", "cover_invites",
            "reallocation_cases", "reallocation_history",
            "notifications", "audit_events", "alembic_version",
        }
        assert expected <= names
        with engine.connect() as conn:
            revision = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert revision == "d5e6f7a8b9c0"
        fks = inspector.get_foreign_keys("enrollments")
        reallocation_fk = next(
            item for item in fks
            if item["constrained_columns"] == ["reallocation_id"]
        )
        assert reallocation_fk["referred_table"] == "reallocation_cases"
        assert reallocation_fk["referred_columns"] == ["id"]
        assert reallocation_fk["options"]["ondelete"] == "RESTRICT"
        indexes = inspector.get_indexes("enrollments")
        assert any(
            item["name"] == "uq_enrollments_session_participant_active"
            and item["unique"]
            for item in indexes
        )
    finally:
        engine.dispose()
