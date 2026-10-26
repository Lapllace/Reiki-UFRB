"""Testes da Fase 2 (SQLite em memória — lógica, não bloqueios PostgreSQL).

PENDENTE no PostgreSQL: concorrência (FOR UPDATE), índice parcial único,
migração real. Marcados com pytest.mark.postgres_pending.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.phase2 import Enrollment, EnrollmentStatus, WeeklyAvailability
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.services import phase2_service

WS = date(2026, 10, 26)  # segunda-feira

pytestmark_postgres = pytest.mark.postgres_pending


def _setup_cycle(db, phase=CyclePhase.COLLECTING_AVAILABILITY):
    return WeeklyCycle(week_start=WS, phase=phase)


def _make_instructor(db, n=1) -> User:
    u = User(
        name=f"Instrutor {n}",
        email=f"instrutor{n}@x.local",
        password_hash="x",
        role=Role.INSTRUCTOR,
    )
    db.add(u)
    return u


def _entries(days=2):
    base = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)
    return [
        {
            "kind": "available",
            "starts_at": base + timedelta(days=i),
            "ends_at": base + timedelta(days=i, hours=1),
            "location_id": None,
            "note": None,
        }
        for i in range(days)
    ]


# ------------------------- Disponibilidade -------------------------


def test_submit_availability(db) -> None:
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    sub = phase2_service.submit_availability(
        db, instr, WS, unavailable=False, entries=_entries()
    )
    assert sub.status.value == "submitted"
    assert len(sub.entries) == 2
    # Upsert: submeter de novo atualiza em vez de duplicar.
    sub2 = phase2_service.submit_availability(
        db, instr, WS, unavailable=False, entries=_entries(1)
    )
    assert sub2.id == sub.id
    assert len(sub2.entries) == 1


def test_declare_unavailable(db) -> None:
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    sub = phase2_service.submit_availability(
        db, instr, WS, unavailable=True, entries=[]
    )
    assert sub.status.value == "unavailable"
    assert sub.entries == []


def test_duplicate_submission_same_week_upserts(db) -> None:
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    phase2_service.submit_availability(db, instr, WS, unavailable=False, entries=_entries())
    phase2_service.submit_availability(db, instr, WS, unavailable=True, entries=[])
    rows = db.query(WeeklyAvailability).all()
    assert len(rows) == 1
    assert rows[0].status.value == "unavailable"


def test_invalid_entries_rejected(db) -> None:
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    with pytest.raises(phase2_service.AvailabilityError):
        phase2_service.submit_availability(
            db, instr, WS, unavailable=False, entries=[]
        )
    bad = [
        {
            "kind": "available",
            "starts_at": datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc),
            "ends_at": datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc),
            "location_id": None,
            "note": None,
        }
    ]
    with pytest.raises(phase2_service.AvailabilityError):
        phase2_service.submit_availability(db, instr, WS, unavailable=False, entries=bad)


def test_agenda_requires_all_instructors(db) -> None:
    cycle = _setup_cycle(db)
    db.add(cycle)
    i1 = _make_instructor(db, 1)
    i2 = _make_instructor(db, 2)
    db.commit()
    phase2_service.submit_availability(db, i1, WS, unavailable=False, entries=_entries())
    assert not phase2_service.all_instructors_submitted(db, cycle)
    phase2_service.submit_availability(db, i2, WS, unavailable=True, entries=[])
    assert phase2_service.all_instructors_submitted(db, cycle)
    phase2_service.publish_week(db, WS)
    db.refresh(cycle)
    assert cycle.phase == CyclePhase.ENROLLMENT_PENDING
    # Idempotente: publicar de novo não muda de fase de novo.
    cycle2 = phase2_service.publish_week(db, WS)
    assert cycle2.phase == CyclePhase.ENROLLMENT_PENDING


def test_publish_requires_capacity_set(db) -> None:
    """Publicação da agenda não exige capacidade; inscrição confirmada, sim."""
    cycle = _setup_cycle(db)
    db.add(cycle)
    i1 = _make_instructor(db, 1)
    db.commit()
    phase2_service.submit_availability(db, i1, WS, unavailable=True, entries=[])
    phase2_service.publish_week(db, WS)  # publica sem erro mesmo sem sessões


def test_availability_locked_after_phase(db) -> None:
    db.add(_setup_cycle(db, phase=CyclePhase.ENROLLMENT_OPEN))
    instr = _make_instructor(db)
    db.commit()
    with pytest.raises(phase2_service.AvailabilityError) as exc:
        phase2_service.submit_availability(
            db, instr, WS, unavailable=True, entries=[]
        )
    assert exc.value.code == "locked"


def test_pending_is_not_unavailable(db) -> None:
    """Ausência de submissão ≠ indisponibilidade."""
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    sub = phase2_service.get_availability(db, instr.id, WS)
    assert sub is None  # pending é derivado, não registro


# --------------------------- Inscrições ---------------------------


def _make_session(db, loc=None, capacity=2, status=SessionStatus.OPEN, phase=CyclePhase.ENROLLMENT_OPEN):
    if loc is None:
        loc = Location(name=f"Sala {uuid.uuid4().hex[:6]}")
        db.add(loc)
    db.add(_setup_cycle(db, phase))
    db.flush()  # garante ids para as FKs
    s = ReikiSession(
        location_id=loc.id,
        starts_at=datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc),
        capacity=capacity,
        status=status,
    )
    db.add(s)
    db.commit()
    return s


def _make_participant(db, n=None) -> User:
    u = User(
        name=f"Participante {n or uuid.uuid4().hex[:6]}",
        email=f"p{uuid.uuid4().hex[:8]}@x.local",
        password_hash="x",
        role=Role.PARTICIPANT,
    )
    db.add(u)
    db.commit()
    return u


def test_create_enrollment_confirmed(db) -> None:
    s = _make_session(db, capacity=2)
    p = _make_participant(db)
    enr = phase2_service.create_enrollment(db, p, s.id)
    assert enr.status == EnrollmentStatus.CONFIRMED
    assert enr.waitlist_position is None
    assert enr.created_at is not None


def test_capacity_undefined_blocks(db) -> None:
    s = _make_session(db, capacity=None)
    p = _make_participant(db)
    with pytest.raises(phase2_service.EnrollmentError) as exc:
        phase2_service.create_enrollment(db, p, s.id)
    assert exc.value.code == "capacity_undefined"


def test_session_full_waitlist_ordering(db) -> None:
    s = _make_session(db, capacity=1)
    p1 = _make_participant(db)
    p2 = _make_participant(db)
    p3 = _make_participant(db)
    e1 = phase2_service.create_enrollment(db, p1, s.id)
    assert e1.status == EnrollmentStatus.CONFIRMED
    e2 = phase2_service.create_enrollment(db, p2, s.id)
    assert e2.status == EnrollmentStatus.WAITLISTED
    assert e2.waitlist_position == 1
    assert s.status == "full"
    e3 = phase2_service.create_enrollment(db, p3, s.id)
    assert e3.waitlist_position == 2


def test_duplicate_active_enrollment_blocked(db) -> None:
    s = _make_session(db, capacity=5)
    p = _make_participant(db)
    phase2_service.create_enrollment(db, p, s.id)
    with pytest.raises(phase2_service.EnrollmentError) as exc:
        phase2_service.create_enrollment(db, p, s.id)
    assert exc.value.code == "duplicate"


def test_cancel_promotes_next_in_line(db) -> None:
    s = _make_session(db, capacity=1)
    p1 = _make_participant(db)
    p2 = _make_participant(db)
    p3 = _make_participant(db)
    e1 = phase2_service.create_enrollment(db, p1, s.id)
    e2 = phase2_service.create_enrollment(db, p2, s.id)
    e3 = phase2_service.create_enrollment(db, p3, s.id)
    assert e2.waitlist_position == 1 and e3.waitlist_position == 2
    phase2_service.cancel_enrollment(db, p1, e1.id)
    db.refresh(e2)
    db.refresh(e3)
    assert e2.status == EnrollmentStatus.CONFIRMED
    assert e2.waitlist_position is None
    assert e3.waitlist_position == 1
    # Cancelamento de cancelada é rejeitado.
    with pytest.raises(phase2_service.EnrollmentError):
        phase2_service.cancel_enrollment(db, p1, e1.id)


def test_cancel_not_cancellable_states(db) -> None:
    s = _make_session(db, capacity=5)
    p = _make_participant(db)
    e = phase2_service.create_enrollment(db, p, s.id)
    e.status = EnrollmentStatus.ATTENDED
    db.commit()
    with pytest.raises(phase2_service.EnrollmentError) as exc:
        phase2_service.cancel_enrollment(db, p, e.id)
    assert exc.value.code == "not_cancellable"


def test_enrollment_in_scheduled_session_rejected(db) -> None:
    s = _make_session(db, capacity=5, status=SessionStatus.SCHEDULED)
    p = _make_participant(db)
    with pytest.raises(phase2_service.EnrollmentError) as exc:
        phase2_service.create_enrollment(db, p, s.id)
    assert exc.value.code == "not_open"


@pytest.mark.postgres_pending
def test_concurrent_enrollment_no_double_booking(postgres_db, postgres_session_factory) -> None:
    session_row = _make_session(postgres_db, capacity=1)
    participants = [_make_participant(postgres_db, n=i) for i in range(2)]
    participant_ids = [item.id for item in participants]
    postgres_db.commit()
    barrier = __import__("threading").Barrier(2)

    def attempt(participant_id):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            participant = db.get(User, participant_id)
            enrollment = phase2_service.create_enrollment(db, participant, session_row.id)
            db.commit()
            return enrollment.status
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, participant_ids))
    assert all(not isinstance(result, Exception) for result in results)
    rows = postgres_db.scalars(
        select(Enrollment).where(Enrollment.session_id == session_row.id)
    ).all()
    assert sum(row.status == EnrollmentStatus.CONFIRMED for row in rows) == 1
    assert sum(row.status == EnrollmentStatus.WAITLISTED for row in rows) == 1
    assert sorted(row.waitlist_position for row in rows if row.status == EnrollmentStatus.WAITLISTED) == [1]
    confirmed = next(row for row in rows if row.status == EnrollmentStatus.CONFIRMED)
    confirmed_participant = postgres_db.get(User, confirmed.participant_id)
    phase2_service.cancel_enrollment(postgres_db, confirmed_participant, confirmed.id)
    postgres_db.commit()
    promoted = postgres_db.scalars(
        select(Enrollment).where(Enrollment.session_id == session_row.id)
    ).all()
    assert sum(row.status == EnrollmentStatus.CONFIRMED for row in promoted) == 1
    assert sum(row.status == EnrollmentStatus.WAITLISTED for row in promoted) == 0


@pytest.mark.postgres_pending
def test_partial_unique_index_enforced(postgres_db) -> None:
    session_row = _make_session(postgres_db, capacity=2)
    participant = _make_participant(postgres_db)
    first = phase2_service.create_enrollment(postgres_db, participant, session_row.id)
    postgres_db.commit()
    duplicate = Enrollment(
        session_id=session_row.id,
        participant_id=participant.id,
        status=EnrollmentStatus.CONFIRMED,
    )
    postgres_db.add(duplicate)
    with pytest.raises(IntegrityError):
        postgres_db.commit()
    postgres_db.rollback()
    assert postgres_db.get(Enrollment, first.id) is not None
    indexes = inspect(postgres_db.bind).get_indexes("enrollments")
    assert any(item["name"] == "uq_enrollments_session_participant_active" for item in indexes)
