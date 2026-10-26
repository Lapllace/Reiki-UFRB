"""Fase 4: reorganização, prioridade futura e sessões extras."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.location import Location
from app.models.phase2 import Enrollment, EnrollmentStatus
from app.models.phase4 import ReallocationAlternative, ReallocationCase, ReallocationStatus
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.schemas.phase4 import CreateExtraSessionIn
from app.services import cover_service, phase2_service, phase4_service
from tests.conftest import login
from tests.test_auth import PASSWORD
from tests.test_phase2 import _make_session
from tests.test_phase3 import _instructor, _owned_session


def _coordinator(db) -> User:
    user = User(
        name="Coordenação",
        email=f"coord-{uuid.uuid4().hex[:8]}@x.local",
        password_hash=hash_password(PASSWORD),
        role=Role.COORDINATOR,
    )
    db.add(user)
    db.commit()
    return user


def _participant(db) -> User:
    user = User(
        name="Participante",
        email=f"part-{uuid.uuid4().hex[:8]}@x.local",
        password_hash=hash_password(PASSWORD),
        role=Role.PARTICIPANT,
    )
    db.add(user)
    db.commit()
    return user


def _uncovered_case(db):
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session.id)
    db.commit()
    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()
    cases = phase4_service.create_cases_for_uncovered_session(db, session.id)
    db.commit()
    return session, participant, enrollment, cases[0]


def test_uncovered_identifies_participants_and_is_idempotent(db) -> None:
    session, _participant_row, enrollment, case = _uncovered_case(db)
    cases = phase4_service.create_cases_for_uncovered_session(db, session.id)
    assert len(cases) == 1
    assert case.origin_enrollment_id == enrollment.id
    assert case.status == ReallocationStatus.PENDING


def test_uncovered_flow_creates_case_without_manual_transfer(db) -> None:
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    phase2_service.create_enrollment(db, participant, session.id)
    db.commit()
    request = cover_service.cancel_session(db, owner, session.id)
    assert request.status.value == "uncovered"
    assert db.query(ReallocationCase).filter(
        ReallocationCase.origin_session_id == session.id
    ).count() == 1


def test_create_extra_session_requires_capacity_and_active_location(db) -> None:
    coordinator = _coordinator(db)
    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    start = datetime.now(UTC) + timedelta(days=1)
    extra = phase4_service.create_extra_session(
        db, coordinator, starts_at=start, ends_at=start + timedelta(hours=1),
        location_id=location.id, capacity=2,
    )
    assert extra.is_extra is True
    assert extra.status == SessionStatus.SCHEDULED
    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.create_extra_session(
            db, coordinator, starts_at=start, ends_at=start + timedelta(hours=1),
            location_id=location.id, capacity=0,
        )
    assert exc.value.code == "invalid_capacity"


def test_extra_session_schema_requires_timezone_and_valid_period() -> None:
    with pytest.raises(ValueError):
        CreateExtraSessionIn.model_validate({
            "startsAt": "2026-11-04T14:00:00",
            "endsAt": "2026-11-04T15:00:00Z",
            "locationId": str(uuid.uuid4()),
            "capacity": 1,
        })
    with pytest.raises(ValueError):
        CreateExtraSessionIn.model_validate({
            "startsAt": "2026-11-04T15:00:00Z",
            "endsAt": "2026-11-04T14:00:00Z",
            "locationId": str(uuid.uuid4()),
            "capacity": 1,
        })


def test_enrollment_reallocation_has_restrict_foreign_key() -> None:
    foreign_keys = Enrollment.__table__.c.reallocation_id.foreign_keys
    assert any(
        key.target_fullname == "reallocation_cases.id"
        and key.ondelete == "RESTRICT"
        for key in foreign_keys
    )


def test_apply_extra_session_preserves_origin_and_blocks_duplicate(db) -> None:
    _origin, participant, enrollment, case = _uncovered_case(db)
    coordinator = _coordinator(db)
    location = Location(name=f"Destino {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()
    applied = phase4_service.apply_reallocation(
        db, coordinator, case.id,
        alternative=ReallocationAlternative.EXTRA_SESSION,
        target_session_id=target.id,
    )
    db.commit()
    moved = db.query(Enrollment).filter(Enrollment.session_id == target.id).one()
    assert applied.status == ReallocationStatus.APPLIED
    assert moved.participant_id == participant.id
    assert moved.reallocation_id == case.id
    assert enrollment.session_id == case.origin_session_id
    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.apply_reallocation(
            db, coordinator, case.id,
            alternative=ReallocationAlternative.EXTRA_SESSION,
            target_session_id=target.id,
        )
    assert exc.value.code == "already_decided"


def test_full_target_rolls_back_case(db) -> None:
    _origin, participant, _enrollment, case = _uncovered_case(db)
    coordinator = _coordinator(db)
    location = Location(name=f"Lotada {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.flush()
    target = ReikiSession(
        location_id=location.id,
        starts_at=datetime.now(UTC) + timedelta(days=3),
        ends_at=datetime.now(UTC) + timedelta(days=3, hours=1),
        capacity=1,
        status=SessionStatus.OPEN,
        is_extra=True,
    )
    db.add(target)
    db.commit()
    other = _participant(db)
    phase2_service.create_enrollment(db, other, target.id)
    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.apply_reallocation(
            db, coordinator, case.id,
            alternative=ReallocationAlternative.EXTRA_SESSION,
            target_session_id=target.id,
        )
    db.rollback()
    assert exc.value.code == "target_full"
    assert db.get(ReallocationCase, case.id).status == ReallocationStatus.PENDING
    assert not db.query(Enrollment).filter(
        Enrollment.session_id == target.id,
        Enrollment.participant_id == participant.id,
    ).count()


def test_future_priority_is_explicit_and_auditable(db) -> None:
    _origin, _participant_row, _enrollment, case = _uncovered_case(db)
    coordinator = _coordinator(db)
    result = phase4_service.apply_reallocation(
        db, coordinator, case.id,
        alternative=ReallocationAlternative.FUTURE_PRIORITY,
    )
    db.commit()
    assert result.status == ReallocationStatus.APPLIED
    assert result.priority_granted_at is not None
    assert result.history[-1].action == "priority_granted"


def test_dismiss_preserves_case_history_and_api_permissions(client: TestClient, db) -> None:
    _origin, _participant_row, _enrollment, case = _uncovered_case(db)
    coordinator = _coordinator(db)
    participant = _participant(db)
    login(client, participant.email, PASSWORD)
    response = client.get("/coordination/reallocations")
    assert response.status_code == 403
    login(client, coordinator.email, PASSWORD)
    response = client.post(f"/coordination/reallocations/{case.id}/dismiss", json={"reason": "sem alternativa"})
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    db.refresh(case)
    assert case.status == ReallocationStatus.DISMISSED
    assert case.history[-1].action == "dismissed"


def test_api_extra_session_and_reallocation_are_camel_case(client: TestClient, db) -> None:
    _origin, _participant_row, _enrollment, case = _uncovered_case(db)
    coordinator = _coordinator(db)
    location = Location(name=f"API {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    login(client, coordinator.email, PASSWORD)
    response = client.post(
        "/coordination/sessions/extra",
        json={
            "startsAt": "2026-11-04T14:00:00Z",
            "endsAt": "2026-11-04T15:00:00Z",
            "locationId": str(location.id),
            "capacity": 2,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["isExtra"] is True
    assert "startsAt" in body and "locationId" not in body["location"]
    target_id = body["id"]
    target = db.get(ReikiSession, uuid.UUID(target_id))
    target.status = SessionStatus.OPEN
    db.commit()
    response = client.post(
        f"/coordination/reallocations/{case.id}/apply",
        json={"alternative": "extra_session", "targetSessionId": target_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert "originSession" in body and "participantCount" in body


@pytest.mark.postgres_pending
def test_apply_race_one_wins(postgres_db, postgres_session_factory) -> None:
    origin, _participant_one, _enrollment_one, _case_one = _uncovered_case(postgres_db)
    participant_two = _participant(postgres_db)
    phase2_service.create_enrollment(postgres_db, participant_two, origin.id)
    postgres_db.commit()
    cases = phase4_service.create_cases_for_uncovered_session(postgres_db, origin.id)
    postgres_db.commit()
    location = Location(name=f"Race {uuid.uuid4().hex[:6]}", is_active=True)
    postgres_db.add(location)
    postgres_db.flush()
    target = ReikiSession(
        location_id=location.id,
        starts_at=datetime.now(UTC) + timedelta(days=4),
        ends_at=datetime.now(UTC) + timedelta(days=4, hours=1),
        capacity=1,
        status=SessionStatus.OPEN,
        is_extra=True,
    )
    postgres_db.add(target)
    postgres_db.commit()
    case_ids = [case.id for case in cases]
    target_id = target.id
    barrier = Barrier(2)

    def attempt(case_id):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            coordinator = _coordinator(db)
            result = phase4_service.apply_reallocation(
                db, coordinator, case_id,
                alternative=ReallocationAlternative.EXTRA_SESSION,
                target_session_id=target_id,
            )
            db.commit()
            return result.status
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, case_ids))
    assert sum(result == ReallocationStatus.APPLIED for result in results) == 1
    assert sum(isinstance(result, phase4_service.ReallocationError) for result in results) == 1
    assert postgres_db.query(Enrollment).filter(
        Enrollment.session_id == target_id,
        Enrollment.status == EnrollmentStatus.CONFIRMED,
    ).count() == 1
    assert postgres_db.query(ReallocationCase).filter(
        ReallocationCase.status == ReallocationStatus.APPLIED
    ).count() == 1


@pytest.mark.postgres_pending
def test_create_cases_race_is_unique(postgres_db, postgres_session_factory) -> None:
    session_row, owner, _extras = _owned_session(postgres_db)
    participant = _participant(postgres_db)
    enrollment = phase2_service.create_enrollment(postgres_db, participant, session_row.id)
    request = cover_service.cancel_session(postgres_db, owner, session_row.id, "imprevisto")
    request.invites.clear()
    request.status = "uncovered"
    session_row.status = SessionStatus.UNCOVERED
    postgres_db.commit()
    enrollment_id = enrollment.id
    session_id = session_row.id
    barrier = Barrier(2)

    def attempt(_):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            cases = phase4_service.create_cases_for_uncovered_session(db, session_id)
            db.commit()
            return cases[0].id
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert all(not isinstance(result, Exception) for result in results)
    assert len(set(results)) == 1
    assert postgres_db.query(ReallocationCase).filter(
        ReallocationCase.origin_enrollment_id == enrollment_id
    ).count() == 1


@pytest.mark.postgres_pending
def test_invalid_reallocation_fk_rejected(postgres_db) -> None:
    session_row, participant, _enrollment, _case = _uncovered_case(postgres_db)
    invalid = Enrollment(
        session_id=session_row.id,
        participant_id=participant.id,
        reallocation_id=uuid.uuid4(),
        status=EnrollmentStatus.CANCELLED,
    )
    postgres_db.add(invalid)
    with pytest.raises(IntegrityError):
        postgres_db.commit()
    postgres_db.rollback()
