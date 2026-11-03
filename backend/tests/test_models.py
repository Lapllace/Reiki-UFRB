"""Verificações de mapeamento SQLAlchemy e metadados (sem banco)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import relationships  # noqa: F401

from app.db.base import Base
from app.models import (
    AuthSession,
    Location,
    ReikiSession,
    Role,
    User,
    WeeklyCycle,
)


def _mapper(model):
    return inspect(model)


def test_five_models_mapped() -> None:
    for model in (User, Location, AuthSession, WeeklyCycle, ReikiSession):
        mapper = _mapper(model)
        assert mapper.persist_selectable is not None


def test_metadata_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "auth_sessions",
        "locations",
        "notifications",
        "weekly_cycles",
        "reiki_sessions",
        "weekly_availabilities",
        "availability_entries",
        "enrollments",
        "cover_requests",
        "audit_events",
        "cover_invites",
        "reallocation_cases",
        "reallocation_history",
    }


def test_timestamps_present_only_where_expected() -> None:
    expected = {User, Location, WeeklyCycle, ReikiSession}
    for model in expected:
        cols = {c.name for c in model.__table__.columns}
        assert {"created_at", "updated_at"} <= cols, model.__name__
    auth_cols = {c.name for c in AuthSession.__table__.columns}
    assert "created_at" in auth_cols and "updated_at" not in auth_cols


def test_relationships_valid() -> None:
    mapper = _mapper(ReikiSession)
    names = {rel.key for rel in mapper.relationships}
    assert {"location", "instructor", "cycle"} <= names
    # Chaves estrangeiras
    fks = {
        fk.target_fullname
        for col in ReikiSession.__table__.columns
        for fk in col.foreign_keys
    }
    assert {
        "weekly_cycles.id",
        "locations.id",
        "users.id",
    } <= fks


def test_cascade_and_ondelete() -> None:
    for col in AuthSession.__table__.columns:
        for fk in col.foreign_keys:
            if fk.parent.name == "user_id":
                assert fk.ondelete == "CASCADE"
    for col in ReikiSession.__table__.columns:
        for fk in col.foreign_keys:
            if fk.parent.name == "cycle_id":
                assert fk.ondelete == "SET NULL"


def test_role_values_lowercase() -> None:
    assert [r.value for r in Role] == ["participant", "instructor", "coordinator"]


def test_role_persists_value_not_name(sqlite_engine) -> None:
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=sqlite_engine)
    with Session() as db:
        u = User(name="T", email="t@x.local", password_hash="x", role=Role.INSTRUCTOR)
        db.add(u)
        db.commit()
        row = db.connection().execute(
            __import__("sqlalchemy").text(
                "SELECT role FROM users WHERE email = 't@x.local'"
            )
        ).scalar_one()
        assert row == "instructor"  # não "INSTRUCTOR"
