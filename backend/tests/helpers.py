"""Fun??es compartilhadas pelos testes das fases 2, 3 e 4."""

import uuid
from datetime import date, datetime, timezone

from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User


WS = date(2026, 10, 26)  # segunda-feira


def _setup_cycle(db, phase=CyclePhase.COLLECTING_AVAILABILITY):
    return WeeklyCycle(week_start=WS, phase=phase)


def _make_session(
    db,
    loc=None,
    capacity=2,
    status=SessionStatus.OPEN,
    phase=CyclePhase.ENROLLMENT_OPEN,
):
    if loc is None:
        loc = Location(name=f"Sala {uuid.uuid4().hex[:6]}")
        db.add(loc)

    db.add(_setup_cycle(db, phase))
    db.flush()

    session = ReikiSession(
        location_id=loc.id,
        starts_at=datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc),
        capacity=capacity,
        status=status,
    )

    db.add(session)
    db.commit()
    return session


def _make_participant(db, n=None) -> User:
    user = User(
        name=f"Participante {n or uuid.uuid4().hex[:6]}",
        email=f"p{uuid.uuid4().hex[:8]}@x.local",
        password_hash="x",
        role=Role.PARTICIPANT,
    )
    db.add(user)
    db.commit()
    return user
