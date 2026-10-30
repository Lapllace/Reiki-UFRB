"""Testes de /locations e /sessions (formato camelCase, semana não publicada)."""

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User


def _make_location(db: Session, name: str = "Sala 1") -> Location:
    loc = Location(name=name)
    db.add(loc)
    db.commit()
    return loc


def test_locations_empty(client: TestClient) -> None:
    resp = client.get("/locations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_locations_returns_active(client: TestClient, db: Session) -> None:
    _make_location(db, "Sala Zen")
    resp = client.get("/locations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    loc = body[0]
    # camelCase
    assert "mapUrl" in loc
    assert set(loc) >= {"id", "name", "address", "reference", "mapUrl", "notes"}


def test_sessions_week_not_published(client: TestClient) -> None:
    # Semana sem ciclo no banco: published=false e nenhuma sessão inventada.
    resp = client.get("/sessions", params={"weekStart": "2026-10-26"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["weekStart"] == "2026-10-26"
    assert body["weekEnd"] == "2026-11-01"
    assert body["sessions"] == []
    assert body["published"] is False


def test_sessions_week_unpublished_phase(client: TestClient, db: Session) -> None:
    db.add(WeeklyCycle(week_start=__import__("datetime").date(2026, 10, 26)))
    db.commit()
    resp = client.get("/sessions", params={"weekStart": "2026-10-26"})
    body = resp.json()
    assert body["published"] is False


def test_sessions_week_published(client: TestClient, db: Session) -> None:
    from datetime import date

    ws = date(2026, 10, 26)
    db.add(WeeklyCycle(week_start=ws, phase=CyclePhase.ENROLLMENT_OPEN))
    db.commit()
    resp = client.get("/sessions", params={"weekStart": ws.isoformat()})
    assert resp.json()["published"] is True


def test_sessions_week_with_sessions_camelcase(
    client: TestClient, db: Session, make_user
) -> None:
    from datetime import date, timedelta

    loc = _make_location(db, "Auditório")
    instructor: User = make_user(role=Role.INSTRUCTOR)
    ws = date(2026, 10, 26)
    db.add(WeeklyCycle(week_start=ws, phase=CyclePhase.ENROLLMENT_OPEN))
    starts = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)
    db.add(
        ReikiSession(
            cycle_id=None,
            location_id=loc.id,
            instructor_id=instructor.id,
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            capacity=None,
            status=SessionStatus.OPEN,
            is_extra=False,
        )
    )
    db.commit()
    resp = client.get("/sessions", params={"weekStart": ws.isoformat()})
    assert resp.status_code == 200
    body = resp.json()
    assert body["published"] is True
    sess = body["sessions"][0]
    assert set(sess) >= {
        "id", "startsAt", "endsAt", "location", "instructor",
        "capacity", "confirmedCount", "waitlistCount", "status", "isExtra",
    }
    assert sess["instructor"]["name"] == instructor.name
    assert sess["location"]["name"] == "Auditório"
    # ISO 8601 com fuso: garantido pelo PostgreSQL (TIMESTAMP WITH TIME ZONE).
    # SQLite nos testes unitários guarda naive, então aqui validamos só ISO 8601.
    assert "T" in sess["startsAt"]


def test_sessions_invalid_weekstart(client: TestClient) -> None:
    resp = client.get("/sessions", params={"weekStart": "26-10-2026"})
    assert resp.status_code == 422


def test_week_start_normalizes_to_monday(client: TestClient) -> None:
    # Quarta-feira 2026-10-28 normaliza para segunda 2026-10-26.
    resp = client.get("/sessions", params={"weekStart": "2026-10-28"})
    body = resp.json()
    assert body["weekStart"] == "2026-10-26"
