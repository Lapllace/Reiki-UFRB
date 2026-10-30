"""Testes da Fase 2 (SQLite em memória — lógica, não bloqueios PostgreSQL).

PENDENTE no PostgreSQL: concorrência (FOR UPDATE), índice parcial único,
migração real. Marcados com pytest.mark.postgres_pending.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.phase2 import (
    AvailabilityStatus,
    Enrollment,
    EnrollmentStatus,
    WeeklyAvailability,
)
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.services import phase2_service
from tests.conftest import login
from tests.test_auth import PASSWORD

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


def _utc_timestamp(value: str | datetime, fallback_tz: timezone | None = None) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        parsed = value
    if parsed.tzinfo is None:
        if fallback_tz is not None:
            parsed = parsed.replace(tzinfo=fallback_tz)
        else:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def test_availability_api_contract_round_trip(client, db, make_user) -> None:
    instructor = make_user(role=Role.INSTRUCTOR, password=PASSWORD)
    today = date.today()
    week_start = phase2_service.week_start_of(today) + timedelta(days=7)
    db.add(
        WeeklyCycle(
            week_start=week_start,
            phase=CyclePhase.COLLECTING_AVAILABILITY,
        )
    )
    db.commit()

    login_response = client.post(
        "/auth/login",
        json={"email": instructor.email, "password": PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text

    starts_at = datetime.combine(
        week_start + timedelta(days=1),
        datetime.min.time().replace(hour=14),
        tzinfo=timezone(timedelta(hours=-3)),
    )
    ends_at = starts_at + timedelta(hours=1)
    payload = {
        "week_start": week_start.isoformat(),
        "unavailable": False,
        "entries": [
            {
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "location_id": None,
                "note": "Disponibilidade no período da tarde.",
            }
        ],
    }

    post_response = client.post("/instructor/availability", json=payload)
    assert post_response.status_code == 200, post_response.text
    post_body = post_response.json()
    assert post_body["weekStart"] == week_start.isoformat()
    assert post_body["status"] == "submitted"
    assert post_body["entries"][0]["kind"] == "available"
    assert _utc_timestamp(post_body["entries"][0]["startsAt"], starts_at.tzinfo) == _utc_timestamp(starts_at)
    assert _utc_timestamp(post_body["entries"][0]["endsAt"], ends_at.tzinfo) == _utc_timestamp(ends_at)
    assert post_body["entries"][0]["locationId"] is None

    get_response = client.get(
        "/instructor/availability",
        params={"weekStart": week_start.isoformat()},
    )
    assert get_response.status_code == 200, get_response.text
    get_body = get_response.json()
    assert get_body["weekStart"] == week_start.isoformat()
    assert get_body["status"] == "submitted"
    assert len(get_body["entries"]) == 1
    assert get_body["entries"][0]["kind"] == "available"
    assert _utc_timestamp(get_body["entries"][0]["startsAt"], starts_at.tzinfo) == _utc_timestamp(starts_at)
    assert _utc_timestamp(get_body["entries"][0]["endsAt"], ends_at.tzinfo) == _utc_timestamp(ends_at)
    assert get_body["entries"][0]["locationId"] is None


def test_submit_availability(db) -> None:
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    sub = phase2_service.submit_availability(
        db, instr, WS, unavailable=False, entries=_entries()
    )
    assert sub.status == "submitted"
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
    assert sub.status == "unavailable"
    assert sub.entries == []


def test_duplicate_submission_same_week_upserts(db) -> None:
    db.add(_setup_cycle(db))
    instr = _make_instructor(db)
    db.commit()
    phase2_service.submit_availability(db, instr, WS, unavailable=False, entries=_entries())
    phase2_service.submit_availability(db, instr, WS, unavailable=True, entries=[])
    rows = db.query(WeeklyAvailability).all()
    assert len(rows) == 1
    assert rows[0].status == "unavailable"


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


@pytest.mark.postgres_pending
def test_publish_week_normalizes_non_monday_date(postgres_db) -> None:
    """Publicar com uma data no meio da semana valida as sessões da semana certa."""
    session_row = _make_session(
        postgres_db,
        capacity=None,
        phase=CyclePhase.COLLECTING_AVAILABILITY,
    )
    instructor = _make_instructor(postgres_db, 1)
    postgres_db.flush()
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    postgres_db.add(
        WeeklyAvailability(
            cycle_id=cycle.id,
            instructor_id=instructor.id,
            status=AvailabilityStatus.SUBMITTED,
            submitted_at=datetime.now(UTC),
        )
    )
    postgres_db.commit()

    # Quinta-feira: a sessão de quarta (28/10) pertence à semana de 26/10.
    midweek = WS + timedelta(days=3)
    with pytest.raises(phase2_service.AvailabilityError) as exc:
        phase2_service.publish_week(postgres_db, midweek)
    assert exc.value.code == "capacity_undefined"
    assert str(session_row.id) in str(exc.value)

    session_row.capacity = 1
    postgres_db.commit()
    published = phase2_service.publish_week(postgres_db, midweek)
    assert published.phase == CyclePhase.ENROLLMENT_PENDING


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


def test_cancel_confirmed_releases_slot_and_promotes_next(db_autoflush) -> None:
    """Cancelar CONFIRMED libera vaga e promove a próxima pessoa da fila."""
    s = _make_session(db_autoflush, capacity=1)
    p1 = _make_participant(db_autoflush)
    p2 = _make_participant(db_autoflush)
    p3 = _make_participant(db_autoflush)
    e1 = phase2_service.create_enrollment(db_autoflush, p1, s.id)
    e2 = phase2_service.create_enrollment(db_autoflush, p2, s.id)
    e3 = phase2_service.create_enrollment(db_autoflush, p3, s.id)
    assert e1.status == EnrollmentStatus.CONFIRMED
    assert e2.waitlist_position == 1 and e3.waitlist_position == 2

    phase2_service.cancel_enrollment(db_autoflush, p1, e1.id)
    db_autoflush.commit()

    db_autoflush.refresh(e1)
    db_autoflush.refresh(e2)
    db_autoflush.refresh(e3)
    assert e1.status == EnrollmentStatus.CANCELLED
    assert e1.cancelled_at is not None
    assert e2.status == EnrollmentStatus.CONFIRMED
    assert e2.waitlist_position is None
    assert e3.status == EnrollmentStatus.WAITLISTED
    assert e3.waitlist_position == 1
    assert len(db_autoflush.scalars(
        select(Enrollment).where(
            Enrollment.session_id == s.id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    ).all()) == 1
    assert s.status == "full"


def test_cancel_waitlisted_does_not_promote_and_renumbers(db_autoflush) -> None:
    """Cancelar WAITLISTED não promove ninguém e renumera os restantes."""
    s = _make_session(db_autoflush, capacity=1)
    p1 = _make_participant(db_autoflush)
    p2 = _make_participant(db_autoflush)
    p3 = _make_participant(db_autoflush)
    p4 = _make_participant(db_autoflush)
    e1 = phase2_service.create_enrollment(db_autoflush, p1, s.id)
    e2 = phase2_service.create_enrollment(db_autoflush, p2, s.id)
    e3 = phase2_service.create_enrollment(db_autoflush, p3, s.id)
    e4 = phase2_service.create_enrollment(db_autoflush, p4, s.id)
    assert e2.waitlist_position == 1
    assert e3.waitlist_position == 2
    assert e4.waitlist_position == 3

    phase2_service.cancel_enrollment(db_autoflush, p2, e2.id)
    db_autoflush.commit()

    db_autoflush.refresh(e1)
    db_autoflush.refresh(e2)
    db_autoflush.refresh(e3)
    db_autoflush.refresh(e4)
    assert e2.status == EnrollmentStatus.CANCELLED
    assert e2.cancelled_at is not None
    assert e2.waitlist_position is None
    assert e1.status == EnrollmentStatus.CONFIRMED
    assert e3.status == EnrollmentStatus.WAITLISTED
    assert e3.waitlist_position == 1
    assert e4.status == EnrollmentStatus.WAITLISTED
    assert e4.waitlist_position == 2
    assert len(db_autoflush.scalars(
        select(Enrollment).where(
            Enrollment.session_id == s.id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    ).all()) == 1
    assert s.status == "full"


def test_cancel_confirmed_in_uncovered_session_does_not_promote(db) -> None:
    """Sessão sem cobertura permite cancelar, mas não promove ninguém."""
    s = _make_session(db, capacity=1)
    p1 = _make_participant(db)
    p2 = _make_participant(db)
    confirmed = phase2_service.create_enrollment(db, p1, s.id)
    waitlisted = phase2_service.create_enrollment(db, p2, s.id)
    db.commit()
    s.status = SessionStatus.UNCOVERED
    db.commit()

    phase2_service.cancel_enrollment(db, p1, confirmed.id)
    db.commit()

    db.refresh(confirmed)
    db.refresh(waitlisted)
    db.refresh(s)
    assert confirmed.status == EnrollmentStatus.CANCELLED
    assert waitlisted.status == EnrollmentStatus.WAITLISTED
    assert waitlisted.waitlist_position == 1
    assert s.status == SessionStatus.UNCOVERED
    assert len(db.scalars(
        select(Enrollment).where(
            Enrollment.session_id == s.id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    ).all()) == 0


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


def test_enrollment_api_post_returns_complete_contract(client, db, make_user) -> None:
    participant = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    session_row = _make_session(db, capacity=2)
    login(client, participant.email, PASSWORD)

    response = client.post("/enrollments", json={"sessionId": str(session_row.id)})
    assert response.status_code == 201, response.text
    body = response.json()
    enrollment = body["enrollment"]
    assert enrollment["status"] == "confirmed"
    assert enrollment["waitlistPosition"] is None
    assert enrollment["cancelledAt"] is None
    assert enrollment["canCancel"] is True
    assert enrollment["cancelBlockedReason"] is None
    assert enrollment["session"]["id"] == str(session_row.id)
    assert enrollment["session"]["confirmedCount"] == 1
    assert enrollment["session"]["waitlistCount"] == 0
    assert enrollment["session"]["status"] == "open"
    assert enrollment["session"]["isExtra"] is False
    assert enrollment["createdAt"]


def test_enrollment_api_get_after_persistence(client, db, make_user) -> None:
    participant = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    session_row = _make_session(db, capacity=2)
    login(client, participant.email, PASSWORD)

    created = client.post("/enrollments", json={"sessionId": str(session_row.id)})
    assert created.status_code == 201, created.text
    enrollment_id = created.json()["enrollment"]["id"]

    response = client.get("/me/enrollments")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == enrollment_id
    assert rows[0]["status"] == "confirmed"
    assert rows[0]["session"]["confirmedCount"] == 1
    assert rows[0]["session"]["waitlistCount"] == 0


def test_enrollment_api_get_cancelled_enrollment(client, db, make_user) -> None:
    participant = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    session_row = _make_session(db, capacity=2)
    login(client, participant.email, PASSWORD)

    created = client.post("/enrollments", json={"sessionId": str(session_row.id)})
    assert created.status_code == 201, created.text
    enrollment_id = created.json()["enrollment"]["id"]

    cancelled = client.post(f"/enrollments/{enrollment_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["cancelledAt"] is not None
    assert body["waitlistPosition"] is None
    assert body["canCancel"] is False
    assert body["cancelBlockedReason"] == "Inscrição já cancelada ou concluída."

    response = client.get("/me/enrollments")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["id"] == enrollment_id
    assert rows[0]["status"] == "cancelled"
    assert rows[0]["cancelledAt"] is not None
    assert rows[0]["canCancel"] is False


def test_enrollment_api_counts_confirmed_and_waitlist(client, db, make_user) -> None:
    session_row = _make_session(db, capacity=1)
    p1 = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    p2 = make_user(role=Role.PARTICIPANT, password=PASSWORD)
    phase2_service.create_enrollment(db, p1, session_row.id)
    phase2_service.create_enrollment(db, p2, session_row.id)
    db.commit()

    login(client, p1.email, PASSWORD)
    response = client.get("/me/enrollments")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["session"]["confirmedCount"] == 1
    assert rows[0]["session"]["waitlistCount"] == 1


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
def test_concurrent_cancel_last_confirmed_and_new_enrollment(
    postgres_db, postgres_session_factory
) -> None:
    """Cancelar a última vaga confirmada e inscrever alguém disputam a sessão."""
    session_row = _make_session(postgres_db, capacity=1)
    confirmed_participant = _make_participant(postgres_db, n="cancel")
    new_participant = _make_participant(postgres_db, n="novo")
    enrollment = phase2_service.create_enrollment(
        postgres_db, confirmed_participant, session_row.id
    )
    postgres_db.commit()
    barrier = Barrier(2)

    def cancel_last() -> str:
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            participant = db.get(User, confirmed_participant.id)
            phase2_service.cancel_enrollment(db, participant, enrollment.id)
            db.commit()
            return "cancelled"
        except Exception as exc:  # pragma: no cover - aparece na asserção
            db.rollback()
            return exc
        finally:
            db.close()

    def enroll_new() -> Enrollment:
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            participant = db.get(User, new_participant.id)
            created = phase2_service.create_enrollment(db, participant, session_row.id)
            db.commit()
            return created
        except Exception as exc:  # pragma: no cover - aparece na asserção
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel_result = pool.submit(cancel_last)
        enroll_result = pool.submit(enroll_new)
        results = [cancel_result.result(), enroll_result.result()]

    assert all(not isinstance(result, Exception) for result in results), results

    # Evita o identity map obsoleto desta sessão após os commits concorrentes.
    postgres_db.expire_all()
    rows = postgres_db.scalars(
        select(Enrollment).where(Enrollment.session_id == session_row.id)
    ).all()
    active = [
        row
        for row in rows
        if row.status in (EnrollmentStatus.CONFIRMED, EnrollmentStatus.WAITLISTED)
    ]
    confirmed = [row for row in rows if row.status == EnrollmentStatus.CONFIRMED]
    waitlisted = [row for row in rows if row.status == EnrollmentStatus.WAITLISTED]

    # A vaga é de quem se inscreveu, nunca do cancelado; nenhuma fila órfã.
    assert len(confirmed) == 1
    assert confirmed[0].participant_id == new_participant.id
    assert waitlisted == []
    assert all(row.participant_id != confirmed_participant.id for row in active)

    # Nenhuma inscrição ativa duplicada por participante.
    active_per_participant: dict[uuid.UUID, int] = {}
    for row in active:
        active_per_participant[row.participant_id] = (
            active_per_participant.get(row.participant_id, 0) + 1
        )
    assert all(count == 1 for count in active_per_participant.values())

    postgres_db.refresh(session_row)
    assert session_row.capacity == 1
    assert len(confirmed) <= session_row.capacity
    assert session_row.status == "full"
    if len(confirmed) < session_row.capacity:
        assert waitlisted == []

    cancelled = postgres_db.get(Enrollment, enrollment.id)
    assert cancelled.status == EnrollmentStatus.CANCELLED


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


def test_availability_entry_note_limit(db) -> None:
    """Validar limite de 200 caracteres em AvailabilityEntryIn.note."""
    from app.schemas.phase2 import AvailabilityEntryIn, AvailabilityEntryKind
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)

    # Nota válida (200 caracteres)
    valid_note = "x" * 200
    entry = AvailabilityEntryIn(
        kind=AvailabilityEntryKind.AVAILABLE,
        starts_at=base,
        ends_at=base + timedelta(hours=1),
        note=valid_note,
    )
    assert entry.note == valid_note

    # Nota inválida (201 caracteres)
    invalid_note = "x" * 201
    with pytest.raises(ValueError) as exc:
        AvailabilityEntryIn(
            kind=AvailabilityEntryKind.AVAILABLE,
            starts_at=base,
            ends_at=base + timedelta(hours=1),
            note=invalid_note,
        )
    assert "at most 200 characters" in str(exc.value)


def test_publish_availability_note_limit(db) -> None:
    """Validar limite de 500 caracteres em PublishAvailabilityIn.note."""
    from app.schemas.phase2 import PublishAvailabilityIn

    # Nota válida (500 caracteres)
    valid_note = "x" * 500
    payload = PublishAvailabilityIn(
        week_start="2026-10-26",
        unavailable=True,
        note=valid_note,
    )
    assert payload.note == valid_note

    # Nota inválida (501 caracteres)
    invalid_note = "x" * 501
    with pytest.raises(ValueError) as exc:
        PublishAvailabilityIn(
            week_start="2026-10-26",
            unavailable=True,
            note=invalid_note,
        )
    assert "at most 500 characters" in str(exc.value)
