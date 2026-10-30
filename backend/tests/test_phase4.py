"""Fase 4: reorganização, prioridade futura e sessões extras."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
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


def _uncovered_case(db, participant_count: int = 1):
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session.id)
    # Inscrições adicionais só são possíveis com a sessão ainda aberta,
    # ou seja, antes do cancelamento que a torna UNCOVERED.
    for _ in range(participant_count - 1):
        phase2_service.create_enrollment(db, _participant(db), session.id)
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
    assert request.status == "uncovered"
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
    origin, _participant_one, _enrollment_one, _case_one = _uncovered_case(
        postgres_db, participant_count=2
    )
    cases = postgres_db.query(ReallocationCase).filter(
        ReallocationCase.origin_session_id == origin.id
    ).all()
    assert len(cases) == 2
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


def test_reject_relocation_with_nonexistent_origin_enrollment(db) -> None:
    """Rejeitar caso com inscrição de origem inexistente."""
    coordinator = _coordinator(db)
    participant = _participant(db)
    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    case = ReallocationCase(
        origin_session_id=target.id,
        origin_enrollment_id=uuid.uuid4(),  # inscrição inexistente
        participant_id=participant.id,
        status=ReallocationStatus.PENDING,
    )
    db.add(case)
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.apply_reallocation(
            db, coordinator, case.id,
            alternative=ReallocationAlternative.EXTRA_SESSION,
            target_session_id=target.id,
        )
    assert exc.value.code == "origin_enrollment_not_found"


def test_reject_relocation_with_wrong_participant(db) -> None:
    """Rejeitar inscrição de origem pertencente a outro participante."""
    session, owner, _ = _owned_session(db)
    participant1 = _participant(db)
    participant2 = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant1, session.id)
    db.commit()

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    case = phase4_service.create_cases_for_uncovered_session(db, session.id)[0]
    case.participant_id = participant2.id  # participante errado
    db.commit()

    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, _coordinator(db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.apply_reallocation(
            db, _coordinator(db), case.id,
            alternative=ReallocationAlternative.EXTRA_SESSION,
            target_session_id=target.id,
        )
    assert exc.value.code == "origin_access_denied"


def test_reject_relocation_with_nonexistent_origin_session(db) -> None:
    """Rejeitar inscrição de origem pertencente a sessão inexistente."""
    session1, owner1, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session1.id)
    db.commit()

    request = cover_service.cancel_session(db, owner1, session1.id)
    request.invites.clear()
    request.status = "uncovered"
    session1.status = SessionStatus.UNCOVERED
    db.commit()

    case = phase4_service.create_cases_for_uncovered_session(db, session1.id)[0]
    case.origin_session_id = uuid.uuid4()  # sessão inexistente
    db.commit()

    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, _coordinator(db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.apply_reallocation(
            db, _coordinator(db), case.id,
            alternative=ReallocationAlternative.EXTRA_SESSION,
            target_session_id=target.id,
        )
    assert exc.value.code == "origin_session_mismatch"


def test_reallocation_failure_does_not_cancel_origin(db) -> None:
    """Falha ao persistir o destino reverte o cancelamento da origem."""
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session.id)
    db.commit()

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    case = phase4_service.create_cases_for_uncovered_session(db, session.id)[0]
    initial_actions = [item.action for item in case.history]

    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, _coordinator(db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    enrollment_id = enrollment.id
    case_id = case.id
    target_id = target.id

    # Falha real de persistência no INSERT da inscrição de destino, depois
    # que apply_reallocation já marcou a origem como cancelada em memória.
    def fail_destination_insert(mapper, connection, target_enrollment) -> None:
        if target_enrollment.session_id == target_id:
            raise IntegrityError(
                "forced destination persistence failure",
                None,
                RuntimeError("forced destination persistence failure"),
            )

    event.listen(Enrollment, "before_insert", fail_destination_insert)
    try:
        with pytest.raises(IntegrityError):
            phase4_service.apply_reallocation(
                db, _coordinator(db), case.id,
                alternative=ReallocationAlternative.EXTRA_SESSION,
                target_session_id=target.id,
            )
    finally:
        event.remove(Enrollment, "before_insert", fail_destination_insert)

    db.rollback()

    origin = db.get(Enrollment, enrollment_id)
    assert origin.status == EnrollmentStatus.CONFIRMED
    assert origin.cancelled_at is None
    assert origin.cancel_reason is None

    assert db.query(Enrollment).filter(
        Enrollment.session_id == target_id,
        Enrollment.participant_id == participant.id,
        Enrollment.status.in_([
            EnrollmentStatus.CONFIRMED,
            EnrollmentStatus.WAITLISTED,
            EnrollmentStatus.ATTENDED,
        ]),
    ).count() == 0

    reloaded_case = db.get(ReallocationCase, case_id)
    assert reloaded_case.status == ReallocationStatus.PENDING
    assert reloaded_case.alternative is None
    assert reloaded_case.target_session_id is None
    assert reloaded_case.decided_at is None
    assert [item.action for item in reloaded_case.history] == initial_actions
    assert "applied" not in [item.action for item in reloaded_case.history]


def test_future_priority_does_not_create_fictitious_enrollment(db) -> None:
    """Prioridade futura encerra a origem sem criar inscrição fictícia."""
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session.id)
    db.commit()

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    case = phase4_service.create_cases_for_uncovered_session(db, session.id)[0]

    result = phase4_service.apply_reallocation(
        db, _coordinator(db), case.id,
        alternative=ReallocationAlternative.FUTURE_PRIORITY,
    )
    db.commit()

    assert result.status == ReallocationStatus.APPLIED
    assert result.priority_granted_at is not None
    assert result.target_session_id is None
    assert result.alternative == ReallocationAlternative.FUTURE_PRIORITY

    db.refresh(enrollment)
    assert enrollment.status not in (
        EnrollmentStatus.CONFIRMED,
        EnrollmentStatus.WAITLISTED,
    )
    assert enrollment.status == EnrollmentStatus.CANCELLED
    assert enrollment.cancelled_at is not None
    assert enrollment.cancel_reason == "future_priority"
    assert enrollment.reallocation_id is None

    # Não existe inscrição fictícia em nenhuma sessão futura/destino.
    active_enrollments = db.query(Enrollment).filter(
        Enrollment.participant_id == participant.id,
        Enrollment.status.in_([
            EnrollmentStatus.CONFIRMED,
            EnrollmentStatus.WAITLISTED,
            EnrollmentStatus.ATTENDED,
        ]),
    ).count()
    assert active_enrollments == 0
    assert db.query(Enrollment).filter(
        Enrollment.participant_id == participant.id,
        Enrollment.session_id != session.id,
    ).count() == 0

    # Prioridade e histórico permanecem registrados no caso único da origem.
    assert [item.action for item in result.history].count("priority_granted") == 1
    assert db.query(ReallocationCase).filter(
        ReallocationCase.origin_enrollment_id == enrollment.id
    ).count() == 1


def test_waitlisted_enrollment_is_transferred_to_extra_session(db) -> None:
    """Transferir WAITLISTED encerra a origem, renumera a fila e não promove."""
    session, owner, _ = _owned_session(db, capacity=1)
    p1 = _participant(db)
    p2 = _participant(db)
    p3 = _participant(db)
    confirmed = phase2_service.create_enrollment(db, p1, session.id)
    moved_origin = phase2_service.create_enrollment(db, p2, session.id)
    remaining = phase2_service.create_enrollment(db, p3, session.id)
    assert confirmed.status == EnrollmentStatus.CONFIRMED
    assert moved_origin.status == EnrollmentStatus.WAITLISTED
    assert moved_origin.waitlist_position == 1
    assert remaining.waitlist_position == 2
    db.commit()

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    cases = phase4_service.create_cases_for_uncovered_session(db, session.id)
    case = next(item for item in cases if item.participant_id == p2.id)

    location = Location(name=f"Fila extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, _coordinator(db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=2,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    result = phase4_service.apply_reallocation(
        db, _coordinator(db), case.id,
        alternative=ReallocationAlternative.EXTRA_SESSION,
        target_session_id=target.id,
    )
    db.commit()

    db.refresh(moved_origin)
    db.refresh(remaining)
    db.refresh(confirmed)
    assert result.status == ReallocationStatus.APPLIED
    assert moved_origin.status == EnrollmentStatus.CANCELLED
    assert moved_origin.cancelled_at is not None
    assert moved_origin.waitlist_position is None
    assert moved_origin.cancel_reason == "reallocated"

    target_enrollment = db.query(Enrollment).filter(
        Enrollment.session_id == target.id,
        Enrollment.participant_id == p2.id,
        Enrollment.status == EnrollmentStatus.CONFIRMED,
    ).one()
    assert target_enrollment.waitlist_position is None
    assert target_enrollment.reallocation_id == case.id

    # A fila de origem é renumerada após a saída da posição 1.
    assert remaining.status == EnrollmentStatus.WAITLISTED
    assert remaining.waitlist_position == 1

    # A sessão sem cobertura não promove ninguém indevidamente.
    db.refresh(session)
    assert confirmed.status == EnrollmentStatus.CONFIRMED
    assert remaining.status != EnrollmentStatus.CONFIRMED
    assert session.status == SessionStatus.UNCOVERED
    assert db.query(Enrollment).filter(
        Enrollment.session_id == session.id,
        Enrollment.status == EnrollmentStatus.CONFIRMED,
    ).count() == 1


def test_reject_repeated_decision(db) -> None:
    """Rejeitar repetição de uma decisão concluída."""
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session.id)
    db.commit()

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    case = phase4_service.create_cases_for_uncovered_session(db, session.id)[0]

    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, _coordinator(db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    phase4_service.apply_reallocation(
        db, _coordinator(db), case.id,
        alternative=ReallocationAlternative.EXTRA_SESSION,
        target_session_id=target.id,
    )
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.apply_reallocation(
            db, _coordinator(db), case.id,
            alternative=ReallocationAlternative.EXTRA_SESSION,
            target_session_id=target.id,
        )
    assert exc.value.code == "already_decided"

    enrollments = db.query(Enrollment).filter(
        Enrollment.session_id == target.id,
        Enrollment.status == EnrollmentStatus.CONFIRMED
    ).count()
    assert enrollments == 1


def test_history_preserved_after_apply(db) -> None:
    """Confirmar preservação do histórico após aplicação."""
    session, owner, _ = _owned_session(db)
    participant = _participant(db)
    enrollment = phase2_service.create_enrollment(db, participant, session.id)
    db.commit()

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    case = phase4_service.create_cases_for_uncovered_session(db, session.id)[0]
    initial_history_count = len(case.history)

    location = Location(name=f"Extra {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    target = phase4_service.create_extra_session(
        db, _coordinator(db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    db.commit()

    phase4_service.apply_reallocation(
        db, _coordinator(db), case.id,
        alternative=ReallocationAlternative.EXTRA_SESSION,
        target_session_id=target.id,
    )
    db.commit()

    db.refresh(case)
    assert len(case.history) == initial_history_count + 1
    assert case.history[-1].action == "applied"


def test_reject_inactive_location(db) -> None:
    """Rejeitar local inativo."""
    coordinator = _coordinator(db)
    location = Location(name=f"Inativo {uuid.uuid4().hex[:6]}", is_active=False)
    db.add(location)
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.create_extra_session(
            db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
            ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_id=location.id, capacity=2,
        )
    assert exc.value.code == "location_inactive"


def test_reject_nonexistent_location(db) -> None:
    """Rejeitar local inexistente."""
    coordinator = _coordinator(db)

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.create_extra_session(
            db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
            ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_id=uuid.uuid4(), capacity=2,
        )
    assert exc.value.code == "location_inactive"


def test_waitlist_preserves_integrity(db) -> None:
    """Preservar integridade da fila na sessão de origem."""
    session, owner, _ = _owned_session(db, capacity=1)
    participant1 = _participant(db)
    participant2 = _participant(db)

    enrollment1 = phase2_service.create_enrollment(db, participant1, session.id)
    enrollment2 = phase2_service.create_enrollment(db, participant2, session.id)
    db.commit()

    assert enrollment1.status == EnrollmentStatus.CONFIRMED
    assert enrollment2.status == EnrollmentStatus.WAITLISTED
    assert enrollment2.waitlist_position == 1

    request = cover_service.cancel_session(db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    db.commit()

    cases = phase4_service.create_cases_for_uncovered_session(db, session.id)
    assert len(cases) == 2

    db.refresh(enrollment2)
    assert enrollment2.status == EnrollmentStatus.WAITLISTED
    assert enrollment2.waitlist_position == 1


def test_open_scheduled_session(db) -> None:
    """Abrir sessão SCHEDULED com sucesso."""
    coordinator = _coordinator(db)
    location = Location(name=f"Open {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    session = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_id=location.id, capacity=2,
    )
    assert session.status == SessionStatus.SCHEDULED

    opened = phase4_service.open_session(db, coordinator, session.id)
    assert opened.status == SessionStatus.OPEN
    assert opened.id == session.id


def test_reject_open_full_session(db) -> None:
    """Rejeitar abertura de sessão FULL."""
    coordinator = _coordinator(db)
    location = Location(name=f"Full {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    session = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_id=location.id, capacity=1,
    )
    session.status = SessionStatus.FULL
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.open_session(db, coordinator, session.id)
    assert exc.value.code == "session_full"


def test_reject_open_session_without_capacity(db) -> None:
    """Rejeitar abertura de sessão sem capacidade definida."""
    coordinator = _coordinator(db)
    location = Location(name=f"NoCap {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    session = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_id=location.id, capacity=2,
    )
    session.capacity = None  # Remove capacidade após criação
    db.commit()

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.open_session(db, coordinator, session.id)
    assert exc.value.code == "capacity_undefined"


def test_reject_open_session_by_non_coordinator(db) -> None:
    """Rejeitar abertura de sessão por usuário sem papel de coordenador."""
    coordinator = _coordinator(db)
    participant = _participant(db)
    location = Location(name=f"Auth {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    session = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_id=location.id, capacity=2,
    )

    with pytest.raises(phase4_service.ReallocationError) as exc:
        phase4_service.open_session(db, participant, session.id)
    assert exc.value.code == "forbidden"


def test_open_session_logs_audit_event(db) -> None:
    """Registrar evento de auditoria ao abrir sessão."""
    coordinator = _coordinator(db)
    location = Location(name=f"Audit {uuid.uuid4().hex[:6]}", is_active=True)
    db.add(location)
    db.commit()
    session = phase4_service.create_extra_session(
        db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_id=location.id, capacity=2,
    )

    from app.models.phase41 import AuditEvent
    events_before = db.query(AuditEvent).filter(
        AuditEvent.session_id == session.id
    ).count()

    phase4_service.open_session(db, coordinator, session.id)
    db.commit()

    events_after = db.query(AuditEvent).filter(
        AuditEvent.session_id == session.id
    ).count()
    assert events_after == events_before + 1

    event = db.query(AuditEvent).filter(
        AuditEvent.session_id == session.id
    ).order_by(AuditEvent.created_at.desc()).first()
    assert event.kind == "session_opened"
    assert event.actor_id == coordinator.id


@pytest.mark.postgres_pending
def test_open_session_concurrent(postgres_db, postgres_session_factory) -> None:
    """Chamadas concorrentes de abertura não devem duplicar eventos de auditoria."""
    coordinator = _coordinator(postgres_db)
    location = Location(name=f"Race {uuid.uuid4().hex[:6]}", is_active=True)
    postgres_db.add(location)
    postgres_db.commit()
    session = phase4_service.create_extra_session(
        postgres_db, coordinator, starts_at=datetime.now(UTC) + timedelta(days=1),
        ends_at=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_id=location.id, capacity=2,
    )
    postgres_db.commit()
    session_id = session.id
    coordinator_id = coordinator.id
    barrier = Barrier(2)

    def attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            user = db.get(User, coordinator_id)
            phase4_service.open_session(db, user, session_id)
            db.commit()
            return True
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    from app.models.phase41 import AuditEvent
    postgres_db.refresh(session)

    # Exatamente uma chamada deve ter sucesso
    successes = sum(1 for r in results if r is True)
    assert successes == 1, f"Esperado 1 sucesso, obtido {successes}: {results}"

    # A outra deve retornar ReallocationError com código invalid_status
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 1, f"Esperado 1 erro, obtido {len(errors)}: {results}"
    assert isinstance(errors[0], phase4_service.ReallocationError)
    assert errors[0].code == "invalid_status"

    assert session.status == SessionStatus.OPEN

    events = postgres_db.query(AuditEvent).filter(
        AuditEvent.session_id == session_id,
        AuditEvent.kind == "session_opened"
    ).count()
    assert events == 1  # Exatamente um evento, não duplicado


@pytest.mark.postgres_pending
def test_cancel_concurrent_with_reallocation(postgres_db, postgres_session_factory) -> None:
    """Cancelamento concorrente com reorganização não deve causar inconsistências."""
    session, owner, _ = _owned_session(postgres_db, capacity=2)
    participant = _participant(postgres_db)
    enrollment = phase2_service.create_enrollment(postgres_db, participant, session.id)
    postgres_db.commit()

    request = cover_service.cancel_session(postgres_db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    postgres_db.commit()

    case = phase4_service.create_cases_for_uncovered_session(postgres_db, session.id)[0]

    location = Location(name=f"RaceCancel {uuid.uuid4().hex[:6]}", is_active=True)
    postgres_db.add(location)
    postgres_db.commit()
    target = phase4_service.create_extra_session(
        postgres_db, _coordinator(postgres_db), starts_at=datetime.now(UTC) + timedelta(days=2),
        ends_at=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_id=location.id, capacity=1,
    )
    target.status = SessionStatus.OPEN
    postgres_db.commit()

    case_id = case.id
    target_id = target.id
    enrollment_id = enrollment.id
    participant_id = participant.id
    coordinator_id = _coordinator(postgres_db).id
    barrier = Barrier(2)

    def cancel_attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            user = db.get(User, participant_id)
            phase2_service.cancel_enrollment(db, user, enrollment_id, reason="participant_cancel")
            db.commit()
            return "cancelled"
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    def reallocate_attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            user = db.get(User, coordinator_id)
            phase4_service.apply_reallocation(
                db, user, case_id,
                alternative=ReallocationAlternative.EXTRA_SESSION,
                target_session_id=target_id,
            )
            db.commit()
            return "reallocated"
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda f: f(), [cancel_attempt, reallocate_attempt]))

    postgres_db.refresh(enrollment)
    postgres_db.refresh(case)

    # Um dos dois lados vence e o outro falha; nunca ambos.
    successes = [r for r in results if r in ("cancelled", "reallocated")]
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1, f"Esperado 1 sucesso: {results}"
    assert len(errors) == 1, f"Esperado 1 falha: {results}"

    # Nenhuma inscrição ativa pode estar duplicada no destino ou na origem.
    for session_check in (session.id, target_id):
        duplicates = postgres_db.query(Enrollment).filter(
            Enrollment.session_id == session_check,
            Enrollment.participant_id == participant_id,
            Enrollment.status.in_([EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED]),
        ).count()
        assert duplicates <= 1, (
            f"Existe dupla inscrição ativa na sessão {session_check}: {duplicates}"
        )

    # Cenário 1: cancelamento vence
    if "cancelled" in results:
        # Reorganização deve falhar com origin_status_invalid
        error = errors[0]
        assert isinstance(error, phase4_service.ReallocationError)
        assert error.code == "origin_status_invalid"

        # Caso continua PENDING
        postgres_db.refresh(case)
        assert case.status == ReallocationStatus.PENDING

        # Não existe inscrição de destino
        target_enrollments = postgres_db.query(Enrollment).filter(
            Enrollment.session_id == target_id,
            Enrollment.participant_id == participant_id
        ).count()
        assert target_enrollments == 0

        # Inscrição original está cancelada, com motivo registrado
        postgres_db.refresh(enrollment)
        assert enrollment.status == EnrollmentStatus.CANCELLED
        assert enrollment.cancelled_at is not None
        assert enrollment.cancel_reason == "participant_cancel"

        # Nenhuma inscrição ativa remanescente do participante
        active_enrollments = postgres_db.query(Enrollment).filter(
            Enrollment.participant_id == participant_id,
            Enrollment.status.in_([EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED]),
        ).count()
        assert active_enrollments == 0

    # Cenário 2: reorganização vence
    else:
        assert "reallocated" in results
        # Cancelamento deve falhar com not_cancellable
        error = errors[0]
        assert isinstance(error, phase2_service.EnrollmentError)
        assert error.code == "not_cancellable"

        # Caso fica APPLIED
        postgres_db.refresh(case)
        assert case.status == ReallocationStatus.APPLIED

        # Existe exatamente uma inscrição confirmada na sessão extra
        target_enrollments = postgres_db.query(Enrollment).filter(
            Enrollment.session_id == target_id,
            Enrollment.participant_id == participant_id,
            Enrollment.status == EnrollmentStatus.CONFIRMED
        ).count()
        assert target_enrollments == 1, (
            f"Esperada exatamente 1 inscrição confirmada no destino, obtidas {target_enrollments}"
        )

        # Inscrição original encerrada pela reorganização, com motivo registrado
        postgres_db.refresh(enrollment)
        assert enrollment.status == EnrollmentStatus.CANCELLED
        assert enrollment.cancelled_at is not None
        assert enrollment.cancel_reason == "reallocated"

        # Ausência de inscrições ativas duplicadas (origem e total)
        origin_enrollments = postgres_db.query(Enrollment).filter(
            Enrollment.session_id == session.id,
            Enrollment.participant_id == participant_id,
            Enrollment.status.in_([EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED])
        ).count()
        assert origin_enrollments == 0

        active_enrollments = postgres_db.query(Enrollment).filter(
            Enrollment.participant_id == participant_id,
            Enrollment.status.in_([EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED]),
        ).count()
        assert active_enrollments == 1


@pytest.mark.postgres_pending
def test_concurrent_reallocations_renumber_same_origin_waitlist(
    postgres_db, postgres_session_factory
) -> None:
    """Reorganizações concorrentes da mesma fila não podem corromper posições.

    A sessão de origem fica UNCOVERED com uma inscrição confirmada e três na
    fila. Dois participantes da fila são reorganizados ao mesmo tempo para
    sessões extras distintas; ambos os fluxos chamam `renumber_waitlist()`
    sobre a mesma sessão de origem.
    """
    session, owner, _ = _owned_session(postgres_db, capacity=1)
    participants = [_participant(postgres_db) for _ in range(4)]
    enrollments = [
        phase2_service.create_enrollment(postgres_db, participant, session.id)
        for participant in participants
    ]
    postgres_db.commit()

    # Primeira inscrição confirmada; as três seguintes formam a fila 1, 2, 3.
    assert enrollments[0].status == EnrollmentStatus.CONFIRMED
    assert [e.status for e in enrollments[1:]] == [EnrollmentStatus.WAITLISTED] * 3
    assert [e.waitlist_position for e in enrollments[1:]] == [1, 2, 3]

    request = cover_service.cancel_session(postgres_db, owner, session.id)
    request.invites.clear()
    request.status = "uncovered"
    session.status = SessionStatus.UNCOVERED
    postgres_db.commit()

    cases = phase4_service.create_cases_for_uncovered_session(postgres_db, session.id)
    postgres_db.commit()
    cases_by_participant = {case.participant_id: case for case in cases}

    coordinator = _coordinator(postgres_db)
    location = Location(name=f"RaceWaitlist {uuid.uuid4().hex[:6]}", is_active=True)
    postgres_db.add(location)
    postgres_db.commit()
    targets = []
    for offset in range(2):
        start = datetime.now(UTC) + timedelta(days=2, hours=offset)
        target = phase4_service.create_extra_session(
            postgres_db,
            coordinator,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location_id=location.id,
            capacity=1,
        )
        target.status = SessionStatus.OPEN
        targets.append(target)
    postgres_db.commit()

    # Dois participantes da fila, cada um com seu caso e sua sessão de destino.
    selected = participants[1:3]
    selected_enrollments = enrollments[1:3]
    selected_cases = [cases_by_participant[participant.id] for participant in selected]
    barrier = Barrier(2)
    coordinator_id = coordinator.id

    def attempt(case_id, target_id):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            user = db.get(User, coordinator_id)
            phase4_service.apply_reallocation(
                db,
                user,
                case_id,
                alternative=ReallocationAlternative.EXTRA_SESSION,
                target_session_id=target_id,
            )
            db.commit()
            return "applied"
        except Exception as exc:  # noqa: BLE001 - o teste inspeciona o erro
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda pair: attempt(*pair),
                [(case.id, target.id) for case, target in zip(selected_cases, targets)],
            )
        )

    errors = [result for result in results if isinstance(result, Exception)]
    assert not errors, f"Reorganizações concorrentes falharam: {errors!r}"
    assert results == ["applied", "applied"]

    postgres_db.expire_all()

    # Ambos os casos processados e inscrições originais encerradas.
    for participant, enrollment, target in zip(selected, selected_enrollments, targets):
        case = postgres_db.get(ReallocationCase, cases_by_participant[participant.id].id)
        assert case.status == ReallocationStatus.APPLIED

        origin = postgres_db.get(Enrollment, enrollment.id)
        assert origin.status == EnrollmentStatus.CANCELLED
        assert origin.cancelled_at is not None
        assert origin.cancel_reason == "reallocated"
        assert origin.waitlist_position is None

        # Cada destino contém exatamente a inscrição esperada.
        destination = postgres_db.query(Enrollment).filter(
            Enrollment.session_id == target.id,
        ).all()
        assert len(destination) == 1
        assert destination[0].participant_id == participant.id
        assert destination[0].status == EnrollmentStatus.CONFIRMED
        assert destination[0].reallocation_id == case.id

    # Fila restante com posições consecutivas começando em 1.
    remaining = (
        postgres_db.query(Enrollment)
        .filter(
            Enrollment.session_id == session.id,
            Enrollment.status == EnrollmentStatus.WAITLISTED,
        )
        .order_by(Enrollment.waitlist_position)
        .all()
    )
    assert [e.participant_id for e in remaining] == [participants[3].id]
    assert [e.waitlist_position for e in remaining] == list(
        range(1, len(remaining) + 1)
    )

    # Nenhuma inscrição ativa duplicada (por participante e sessão).
    active = (
        postgres_db.query(Enrollment)
        .filter(
            Enrollment.participant_id.in_([participant.id for participant in participants]),
            Enrollment.status.in_(
                [EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED]
            ),
        )
        .all()
    )
    keys = [(e.participant_id, e.session_id) for e in active]
    assert len(keys) == len(set(keys))
    assert len(keys) == 4  # confirmado na origem + 2 reallocados + 1 na fila
