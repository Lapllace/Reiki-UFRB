"""Publicação explícita da agenda e abertura explícita das inscrições.

Cobre as transições de fase do ciclo semanal (Sprint 3) com PostgreSQL real:
publicação não abre inscrições, abertura exige ciclo publicado e ambas as
operações são serializadas pelo bloqueio da linha do ciclo.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier, Event, Thread, current_thread

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.phase2 import (
    AvailabilityEntry,
    AvailabilityStatus,
    Enrollment,
    EnrollmentStatus,
    WeeklyAvailability,
)
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.services import coordination_service, phase2_service, phase4_service, schedule_service
from tests.conftest import login
from tests.test_auth import PASSWORD

# 2026-11-09 é segunda-feira; 2026-11-15 é domingo.
WS = date(2026, 11, 9)
NEXT_WS = WS + timedelta(days=7)

pytestmark = pytest.mark.postgres_pending


@pytest.fixture
def postgres_client(postgres_session_factory):
    """Cliente HTTP apontando para o PostgreSQL real dos testes."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        cors_origins="http://localhost:3000"
    )

    def override_get_db():
        session = postgres_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _make_user(
    db: Session,
    role: Role,
    name: str,
    *,
    active: bool = True,
) -> User:
    user = User(
        name=name,
        email=f"{uuid.uuid4().hex}@teste.local",
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=active,
    )
    db.add(user)
    db.commit()
    return user


def _make_cycle(
    db: Session,
    week_start: date = WS,
    phase: CyclePhase = CyclePhase.COLLECTING_AVAILABILITY,
) -> WeeklyCycle:
    cycle = WeeklyCycle(week_start=week_start, phase=phase)
    db.add(cycle)
    db.commit()
    return cycle


def _make_location(db: Session) -> Location:
    location = Location(name=f"Local {uuid.uuid4().hex[:8]}")
    db.add(location)
    db.commit()
    return location


def _dt(day: date, hour: int = 14, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _make_session(
    db: Session,
    cycle: WeeklyCycle | None,
    *,
    instructor: User | None = None,
    location: Location | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    capacity: int | None = 4,
    status: SessionStatus = SessionStatus.SCHEDULED,
) -> ReikiSession:
    if location is None:
        location = _make_location(db)
    starts_at = starts_at or _dt(WS, 14)
    session = ReikiSession(
        cycle_id=cycle.id if cycle else None,
        instructor_id=instructor.id if instructor else None,
        location_id=location.id,
        starts_at=starts_at,
        ends_at=ends_at or starts_at + timedelta(hours=1),
        capacity=capacity,
        status=status,
        is_extra=False,
    )
    db.add(session)
    db.commit()
    return session


def _submit(
    db: Session,
    instructor: User,
    *,
    week_start: date = WS,
    unavailable: bool = False,
    entries: list[dict] | None = None,
) -> WeeklyAvailability:
    if entries is None and not unavailable:
        entries = [
            {
                "kind": "available",
                "starts_at": _dt(week_start, 14),
                "ends_at": _dt(week_start, 15),
                "location_id": None,
                "note": None,
            }
        ]
    submission = phase2_service.submit_availability(
        db,
        instructor,
        week_start,
        unavailable=unavailable,
        entries=[] if unavailable else entries,
    )
    db.commit()
    return submission


def _make_enrollment(
    db: Session,
    session: ReikiSession,
    participant: User,
    *,
    status: EnrollmentStatus = EnrollmentStatus.CONFIRMED,
) -> Enrollment:
    enrollment = Enrollment(
        session_id=session.id,
        participant_id=participant.id,
        status=status,
    )
    db.add(enrollment)
    db.commit()
    return enrollment


def _publish(client: TestClient, week_start: date = WS, headers: dict | None = None):
    return client.post(
        f"/coordination/cycles/{week_start.isoformat()}/publish",
        headers=headers or {},
    )


def _open(client: TestClient, week_start: date = WS, headers: dict | None = None):
    return client.post(
        f"/coordination/cycles/{week_start.isoformat()}/open-enrollment",
        headers=headers or {},
    )


# ----------------------------- Publicação ----------------------------------


def test_publish_requires_active_instructors_and_keeps_enrollment_closed(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    submitted = _make_user(postgres_db, Role.INSTRUCTOR, "Ofertou")
    unavailable = _make_user(postgres_db, Role.INSTRUCTOR, "Indisponível")
    _make_user(postgres_db, Role.INSTRUCTOR, "Inativo", active=False)
    _submit(postgres_db, submitted)
    _submit(postgres_db, unavailable, unavailable=True)
    session = _make_session(
        postgres_db, cycle, instructor=submitted, capacity=4
    )
    login(postgres_client, coordinator.email, PASSWORD)

    # Domingo normaliza para a segunda-feira da mesma semana.
    response = _publish(postgres_client, WS + timedelta(days=6))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weekStart"] == WS.isoformat()
    assert body["status"] == CyclePhase.ENROLLMENT_PENDING.value

    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )
    # Publicar NÃO abre inscrições: a sessão continua agendada.
    stored = postgres_db.get(ReikiSession, session.id)
    assert stored is not None
    assert stored.status == SessionStatus.SCHEDULED
    # A agenda está publicada (fase), mas ainda não aberta ao público.
    assert schedule_service.is_published(
        postgres_db.get(WeeklyCycle, cycle.id)
    ) is False


def test_publish_rejects_pending_active_instructor(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    submitted = _make_user(postgres_db, Role.INSTRUCTOR, "Ofertou")
    _make_user(postgres_db, Role.INSTRUCTOR, "Sem submissão")
    _submit(postgres_db, submitted)
    _make_session(postgres_db, cycle, instructor=submitted)
    login(postgres_client, coordinator.email, PASSWORD)

    response = _publish(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "incomplete"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.COLLECTING_AVAILABILITY
    )


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("capacity_undefined", "capacity_undefined"),
        ("invalid_capacity", "invalid_capacity"),
        ("outside_week", "outside_week"),
        ("schedule_conflict", "schedule_conflict"),
    ],
)
def test_publish_preserves_agenda_validations(
    postgres_client: TestClient,
    postgres_db: Session,
    case: str,
    expected_code: str,
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    _submit(postgres_db, instructor)
    sessions: list[ReikiSession] = []

    if case == "capacity_undefined":
        sessions.append(
            _make_session(
                postgres_db,
                cycle,
                instructor=instructor,
                location=location,
                capacity=None,
            )
        )
    elif case == "invalid_capacity":
        sessions.append(
            _make_session(
                postgres_db,
                cycle,
                instructor=instructor,
                location=location,
                capacity=0,
            )
        )
    elif case == "invalid_period":
        sessions.append(
            _make_session(
                postgres_db,
                cycle,
                instructor=instructor,
                location=location,
                starts_at=_dt(WS, 15),
                ends_at=_dt(WS, 14),
            )
        )
    elif case == "outside_week":
        sessions.append(
            _make_session(
                postgres_db,
                cycle,
                instructor=instructor,
                location=location,
                # Começa dentro da semana, mas termina depois do limite
                # institucional (segunda 00:00 em America/Bahia).
                starts_at=_dt(WS + timedelta(days=6), 23),
                ends_at=_dt(NEXT_WS, 4),
            )
        )
    else:
        sessions.append(
            _make_session(
                postgres_db,
                cycle,
                instructor=instructor,
                location=location,
                starts_at=_dt(WS, 14),
                ends_at=_dt(WS, 15),
            )
        )
        sessions.append(
            _make_session(
                postgres_db,
                cycle,
                instructor=instructor,
                location=location,
                starts_at=_dt(WS, 14, 30),
                ends_at=_dt(WS, 15, 30),
            )
        )

    login(postgres_client, coordinator.email, PASSWORD)
    response = _publish(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == expected_code
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.COLLECTING_AVAILABILITY
    )
    for session in sessions:
        stored = postgres_db.get(ReikiSession, session.id)
        assert stored is not None
        assert stored.status == SessionStatus.SCHEDULED


@pytest.mark.parametrize(
    ("case", "starts_at", "ends_at"),
    [
        (
            "starts_before_week",
            _dt(WS - timedelta(days=1), 23),
            _dt(WS, 1),
        ),
        (
            "ends_after_week",
            _dt(WS + timedelta(days=6), 23),
            _dt(NEXT_WS, 4),
        ),
    ],
)
def test_publish_rejects_cycle_session_outside_institutional_week(
    postgres_client: TestClient,
    postgres_db: Session,
    case: str,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    """Sessão vinculada ao ciclo não pode escapar da validação por horário.

    A listagem pública filtra pelo início dentro da semana; a publicação não
    pode usar esse mesmo filtro, senão uma sessão do ciclo com horário fora da
    semana seria ignorada.
    """
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    _submit(postgres_db, instructor)
    session = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _publish(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "outside_week"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.COLLECTING_AVAILABILITY
    )
    assert postgres_db.get(ReikiSession, session.id).status == (
        SessionStatus.SCHEDULED
    )


def test_publish_accepts_cycle_session_inside_institutional_week(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    _submit(postgres_db, instructor)
    session = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        starts_at=_dt(WS, 14),
        ends_at=_dt(WS, 15),
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _publish(postgres_client)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == CyclePhase.ENROLLMENT_PENDING.value
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )
    assert postgres_db.get(ReikiSession, session.id).status == (
        SessionStatus.SCHEDULED
    )


def test_session_period_validation_rejects_invalid_period_without_persisting() -> None:
    """Período invertido é rejeitado pela validação compartilhada.

    O banco também possui `ck_reiki_sessions_period`, então uma linha inválida
    não chega a existir; a validação de serviço permanece como defesa.
    """
    invalid = ReikiSession(
        location_id=uuid.uuid4(),
        starts_at=_dt(WS, 15),
        ends_at=_dt(WS, 14),
        capacity=3,
        status=SessionStatus.SCHEDULED,
        is_extra=False,
    )

    with pytest.raises(phase2_service.AvailabilityError) as exc:
        phase2_service._validate_session_periods([invalid], WS)

    assert exc.value.code == "invalid_period"


def test_publish_is_idempotent_and_never_regresses_phase(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    _submit(postgres_db, instructor)
    session = _make_session(postgres_db, cycle, instructor=instructor)
    login(postgres_client, coordinator.email, PASSWORD)

    first = _publish(postgres_client)
    second = _publish(postgres_client)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == CyclePhase.ENROLLMENT_PENDING.value
    assert second.json()["status"] == CyclePhase.ENROLLMENT_PENDING.value
    postgres_db.expire_all()
    assert postgres_db.get(ReikiSession, session.id).status == (
        SessionStatus.SCHEDULED
    )

    # Já em fase posterior: repetir a publicação não volta para pending.
    stored_cycle = postgres_db.get(WeeklyCycle, cycle.id)
    stored_cycle.phase = CyclePhase.ENROLLMENT_OPEN
    postgres_db.commit()

    later = _publish(postgres_client)

    assert later.status_code == 200, later.text
    assert later.json()["status"] == CyclePhase.ENROLLMENT_OPEN.value
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_OPEN
    )


def test_publish_requires_existing_cycle_and_valid_week(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    missing = _publish(postgres_client, NEXT_WS)
    invalid = postgres_client.post("/coordination/cycles/não-é-data/publish")

    assert missing.status_code == 404, missing.text
    assert missing.headers["X-Error-Code"] == "cycle_not_found"
    assert invalid.status_code == 422, invalid.text


def test_publish_requires_coordinator_and_same_origin(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")

    assert _publish(postgres_client).status_code == 401

    login(postgres_client, participant.email, PASSWORD)
    assert _publish(postgres_client).status_code == 403

    postgres_client.post("/auth/logout")
    login(postgres_client, coordinator.email, PASSWORD)
    blocked = _publish(
        postgres_client, headers={"Origin": "http://malicioso.example"}
    )
    assert blocked.status_code == 403


def test_coordinator_can_read_but_not_submit_instructor_availability(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    read = postgres_client.get(
        "/instructor/availability", params={"weekStart": WS.isoformat()}
    )
    blocked = postgres_client.post(
        "/instructor/availability",
        json={"weekStart": WS.isoformat(), "unavailable": True},
    )

    assert read.status_code == 200, read.text
    assert read.json()["status"] == AvailabilityStatus.PENDING.value
    assert blocked.status_code == 403, blocked.text


# ------------------------------- Abertura ----------------------------------


def test_open_enrollment_requires_published_cycle(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    session = _make_session(postgres_db, cycle, instructor=instructor)
    login(postgres_client, coordinator.email, PASSWORD)

    rejected = _open(postgres_client)

    assert rejected.status_code == 409, rejected.text
    assert rejected.headers["X-Error-Code"] == "not_published"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.COLLECTING_AVAILABILITY
    )
    assert postgres_db.get(ReikiSession, session.id).status == (
        SessionStatus.SCHEDULED
    )


def test_open_enrollment_opens_covered_scheduled_sessions(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    session = _make_session(
        postgres_db, cycle, instructor=instructor, capacity=3
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == CyclePhase.ENROLLMENT_OPEN.value
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_OPEN
    )
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.OPEN


def test_enrollment_only_works_after_explicit_opening(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    session = _make_session(
        postgres_db, cycle, instructor=instructor, capacity=1
    )

    login(postgres_client, participant.email, PASSWORD)
    before = postgres_client.post(
        "/enrollments", json={"sessionId": str(session.id)}
    )
    assert before.status_code == 409, before.text
    assert before.headers["X-Error-Code"] == "cycle_not_open"

    postgres_client.post("/auth/logout")
    login(postgres_client, coordinator.email, PASSWORD)
    assert _open(postgres_client).status_code == 200

    postgres_client.post("/auth/logout")
    login(postgres_client, participant.email, PASSWORD)
    after = postgres_client.post(
        "/enrollments", json={"sessionId": str(session.id)}
    )

    assert after.status_code == 201, after.text
    assert after.json()["enrollment"]["status"] == (
        EnrollmentStatus.CONFIRMED.value
    )
    postgres_db.expire_all()
    stored = postgres_db.scalar(
        select(Enrollment).where(Enrollment.session_id == session.id)
    )
    assert stored is not None
    assert stored.participant_id == participant.id
    # Capacidade 1 preenchida: a sessão passa a `full`, sem fechar a fila.
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.FULL


def test_open_enrollment_rejects_empty_agenda(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "empty_agenda"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )


@pytest.mark.parametrize(
    ("capacity", "expected_code"),
    [(None, "capacity_undefined"), (0, "invalid_capacity")],
)
def test_open_enrollment_rejects_invalid_capacity_for_enrollable_sessions(
    postgres_client: TestClient,
    postgres_db: Session,
    capacity: int | None,
    expected_code: str,
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    session = _make_session(
        postgres_db, cycle, instructor=instructor, capacity=capacity
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == expected_code
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )
    assert postgres_db.get(ReikiSession, session.id).status == (
        SessionStatus.SCHEDULED
    )


def test_open_enrollment_rejects_agenda_without_enrollable_sessions(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    location = _make_location(postgres_db)
    needs_cover = _make_session(
        postgres_db,
        cycle,
        location=location,
        starts_at=_dt(WS, 14),
        ends_at=_dt(WS, 15),
        capacity=None,
        status=SessionStatus.NEEDS_COVER,
    )
    uncovered = _make_session(
        postgres_db,
        cycle,
        location=location,
        starts_at=_dt(WS, 16),
        ends_at=_dt(WS, 17),
        capacity=None,
        status=SessionStatus.UNCOVERED,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "no_enrollable_sessions"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )
    assert postgres_db.get(ReikiSession, needs_cover.id).status == (
        SessionStatus.NEEDS_COVER
    )
    assert postgres_db.get(ReikiSession, uncovered.id).status == (
        SessionStatus.UNCOVERED
    )


def test_open_enrollment_preserves_non_enrollable_statuses(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    full_participant = _make_user(
        postgres_db, Role.PARTICIPANT, "Na sessão cheia"
    )
    location = _make_location(postgres_db)
    scheduled = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        location=location,
        starts_at=_dt(WS, 8),
        ends_at=_dt(WS, 9),
        capacity=2,
        status=SessionStatus.SCHEDULED,
    )
    already_open = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        location=location,
        starts_at=_dt(WS, 10),
        ends_at=_dt(WS, 11),
        capacity=2,
        status=SessionStatus.OPEN,
    )
    full = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        location=location,
        starts_at=_dt(WS, 12),
        ends_at=_dt(WS, 13),
        capacity=1,
        status=SessionStatus.FULL,
    )
    _make_enrollment(postgres_db, full, full_participant)
    cancelled = _make_session(
        postgres_db,
        cycle,
        location=location,
        starts_at=_dt(WS, 14),
        ends_at=_dt(WS, 15),
        capacity=None,
        status=SessionStatus.CANCELLED,
    )
    completed = _make_session(
        postgres_db,
        cycle,
        location=location,
        starts_at=_dt(WS, 16),
        ends_at=_dt(WS, 17),
        capacity=None,
        status=SessionStatus.COMPLETED,
    )
    uncovered = _make_session(
        postgres_db,
        cycle,
        location=location,
        starts_at=_dt(WS + timedelta(days=1), 9),
        ends_at=_dt(WS + timedelta(days=1), 10),
        capacity=None,
        status=SessionStatus.UNCOVERED,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 200, response.text
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_OPEN
    )
    assert postgres_db.get(ReikiSession, scheduled.id).status == SessionStatus.OPEN
    assert postgres_db.get(ReikiSession, already_open.id).status == (
        SessionStatus.OPEN
    )
    assert postgres_db.get(ReikiSession, full.id).status == SessionStatus.FULL
    assert postgres_db.get(ReikiSession, cancelled.id).status == (
        SessionStatus.CANCELLED
    )
    assert postgres_db.get(ReikiSession, completed.id).status == (
        SessionStatus.COMPLETED
    )
    assert postgres_db.get(ReikiSession, uncovered.id).status == (
        SessionStatus.UNCOVERED
    )


def test_open_enrollment_reopens_full_session_with_vacancies(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    """`full` sem confirmações suficientes é estado desatualizado, não lotação."""
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    session = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        capacity=2,
        status=SessionStatus.FULL,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 200, response.text
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_OPEN
    )
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.OPEN


def test_open_enrollment_marks_open_session_with_full_capacity_as_full(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    session = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        capacity=1,
        status=SessionStatus.OPEN,
    )
    _make_enrollment(postgres_db, session, participant)
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 200, response.text
    postgres_db.expire_all()
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.FULL


def test_open_enrollment_keeps_exactly_filled_session_full(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    session = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        capacity=1,
        status=SessionStatus.FULL,
    )
    _make_enrollment(postgres_db, session, participant)
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 200, response.text
    postgres_db.expire_all()
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.FULL


def test_open_enrollment_rejects_confirmed_above_capacity_and_rolls_back(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    """Uma sessão inconsistente impede a abertura sem alterar o restante."""
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    valid = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        location=location,
        starts_at=_dt(WS, 8),
        ends_at=_dt(WS, 9),
        capacity=2,
        status=SessionStatus.SCHEDULED,
    )
    inconsistent = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        location=location,
        starts_at=_dt(WS, 10),
        ends_at=_dt(WS, 11),
        capacity=1,
        status=SessionStatus.OPEN,
    )
    first = _make_user(postgres_db, Role.PARTICIPANT, "Primeiro")
    second = _make_user(postgres_db, Role.PARTICIPANT, "Segundo")
    _make_enrollment(postgres_db, inconsistent, first)
    _make_enrollment(postgres_db, inconsistent, second)
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "capacity_exceeded"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )
    # A sessão válida também não sofre alteração parcial.
    assert postgres_db.get(ReikiSession, valid.id).status == (
        SessionStatus.SCHEDULED
    )
    assert postgres_db.get(ReikiSession, inconsistent.id).status == (
        SessionStatus.OPEN
    )
    assert postgres_db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.session_id == inconsistent.id)
    ) == 2


def test_participant_can_enroll_after_full_with_vacancies_is_reopened(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    session = _make_session(
        postgres_db,
        cycle,
        instructor=instructor,
        capacity=2,
        status=SessionStatus.FULL,
    )
    login(postgres_client, coordinator.email, PASSWORD)
    assert _open(postgres_client).status_code == 200
    postgres_db.expire_all()
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.OPEN

    postgres_client.post("/auth/logout")
    login(postgres_client, participant.email, PASSWORD)
    response = postgres_client.post(
        "/enrollments", json={"sessionId": str(session.id)}
    )

    assert response.status_code == 201, response.text
    assert response.json()["enrollment"]["status"] == (
        EnrollmentStatus.CONFIRMED.value
    )
    postgres_db.expire_all()
    assert postgres_db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(
            Enrollment.session_id == session.id,
            Enrollment.status == EnrollmentStatus.CONFIRMED,
        )
    ) == 1
    # Ainda há vaga: a sessão continua aberta após a inscrição.
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.OPEN


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("outside_week", "outside_week"),
        ("schedule_conflict", "schedule_conflict"),
    ],
)
def test_open_enrollment_revalidates_agenda(
    postgres_client: TestClient,
    postgres_db: Session,
    case: str,
    expected_code: str,
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)

    if case == "outside_week":
        _make_session(
            postgres_db,
            cycle,
            instructor=instructor,
            location=location,
            starts_at=_dt(WS - timedelta(days=1), 14),
            ends_at=_dt(WS - timedelta(days=1), 15),
        )
    else:
        _make_session(
            postgres_db,
            cycle,
            instructor=instructor,
            location=location,
            starts_at=_dt(WS, 14),
            ends_at=_dt(WS, 15),
        )
        _make_session(
            postgres_db,
            cycle,
            instructor=instructor,
            location=location,
            starts_at=_dt(WS, 14, 30),
            ends_at=_dt(WS, 15, 30),
        )

    login(postgres_client, coordinator.email, PASSWORD)
    response = _open(postgres_client)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == expected_code
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_PENDING
    )


def test_open_enrollment_is_idempotent_and_does_not_regress_later_phases(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    session = _make_session(postgres_db, cycle, instructor=instructor)
    login(postgres_client, coordinator.email, PASSWORD)

    first = _open(postgres_client)
    second = _open(postgres_client)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == CyclePhase.ENROLLMENT_OPEN.value
    assert second.json()["status"] == CyclePhase.ENROLLMENT_OPEN.value
    postgres_db.expire_all()
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.OPEN

    stored_cycle = postgres_db.get(WeeklyCycle, cycle.id)
    stored_cycle.phase = CyclePhase.IN_PROGRESS
    postgres_db.commit()

    later = _open(postgres_client)

    assert later.status_code == 409, later.text
    assert later.headers["X-Error-Code"] == "invalid_cycle_phase"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == CyclePhase.IN_PROGRESS
    assert postgres_db.get(ReikiSession, session.id).status == SessionStatus.OPEN


def test_open_enrollment_requires_existing_cycle(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    response = _open(postgres_client, NEXT_WS)

    assert response.status_code == 404, response.text
    assert response.headers["X-Error-Code"] == "cycle_not_found"


# ----------------------------- Concorrência --------------------------------


def test_open_enrollment_waits_for_concurrent_publication(
    postgres_db: Session, postgres_session_factory, monkeypatch
) -> None:
    """A abertura espera a publicação terminar e enxerga o ciclo publicado."""
    cycle = _make_cycle(postgres_db)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    _submit(postgres_db, instructor)
    _make_session(postgres_db, cycle, instructor=instructor)

    publication_holds_cycle = Event()
    opener_started = Event()
    original_lock = schedule_service.lock_cycle

    def publication_lock(db: Session, week_start: date):
        locked = original_lock(db, week_start)
        if current_thread().name == "publisher":
            publication_holds_cycle.set()
            assert opener_started.wait(timeout=10), "abertura não iniciou"
        return locked

    monkeypatch.setattr(schedule_service, "lock_cycle", publication_lock)

    def publish() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            locked = phase2_service.publish_week(db, WS)
            db.commit()
            return ("ok", locked.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    def open_enrollment() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            assert publication_holds_cycle.wait(timeout=10), "publicação não iniciou"
            opener_started.set()
            locked = phase2_service.open_enrollment(db, WS)
            db.commit()
            return ("ok", locked.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    results: dict[str, tuple[str, object]] = {}
    publish_thread = Thread(
        target=lambda: results.update(publish=publish()), name="publisher"
    )
    open_thread = Thread(target=lambda: results.update(open=open_enrollment()))
    publish_thread.start()
    open_thread.start()
    publish_thread.join(timeout=30)
    open_thread.join(timeout=30)
    assert not publish_thread.is_alive()
    assert not open_thread.is_alive()

    assert results["publish"] == (
        "ok",
        CyclePhase.ENROLLMENT_PENDING.value,
    ), results["publish"]
    assert results["open"] == (
        "ok",
        CyclePhase.ENROLLMENT_OPEN.value,
    ), results["open"]

    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == (
        CyclePhase.ENROLLMENT_OPEN
    )


def test_concurrent_overlapping_offers_same_instructor_creates_single_session(
    postgres_db: Session, postgres_session_factory
) -> None:
    """Duas ofertas sobrepostas do mesmo ministrante: uma sessão, um conflito."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    first_location = _make_location(postgres_db)
    second_location = _make_location(postgres_db)
    starts_at = _dt(WS, 14)
    submission = _submit(
        postgres_db,
        instructor,
        entries=[
            {
                "kind": "available",
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(hours=1),
                "location_id": first_location.id,
                "note": None,
            },
            {
                "kind": "available",
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(hours=1),
                "location_id": second_location.id,
                "note": None,
            },
        ],
    )
    entry_ids = [entry.id for entry in submission.entries]
    coordinator_id = coordinator.id
    barrier = Barrier(2)

    def attempt(entry_id):
        db = postgres_session_factory()
        try:
            actor = db.get(User, coordinator_id)
            barrier.wait(timeout=10)
            session = coordination_service.create_regular_session(
                db,
                actor,
                WS,
                availability_entry_id=entry_id,
                capacity=3,
            )
            db.commit()
            return ("ok", session.id)
        except coordination_service.CoordinationError as exc:
            db.rollback()
            return ("error", exc.code)
        except Exception as exc:  # pragma: no cover - diagnóstico
            db.rollback()
            return ("unexpected", repr(exc))
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, entry_ids))

    assert sorted(result[0] for result in results) == ["error", "ok"], results
    errors = [result for result in results if result[0] == "error"]
    assert errors[0][1] == "instructor_conflict", results
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 1


def test_concurrent_same_location_offers_different_instructors_single_session(
    postgres_db: Session, postgres_session_factory
) -> None:
    """Ofertas de ministrantes diferentes no mesmo local/horário: só uma sessão."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    first_instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Primeiro")
    second_instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Segundo")
    location = _make_location(postgres_db)
    starts_at = _dt(WS, 16)
    entries = [
        {
            "kind": "available",
            "starts_at": starts_at,
            "ends_at": starts_at + timedelta(hours=1),
            "location_id": location.id,
            "note": None,
        }
    ]
    first_submission = _submit(
        postgres_db, first_instructor, entries=entries
    )
    second_submission = _submit(
        postgres_db, second_instructor, entries=entries
    )
    entry_ids = [
        first_submission.entries[0].id,
        second_submission.entries[0].id,
    ]
    coordinator_id = coordinator.id
    barrier = Barrier(2)

    def attempt(entry_id):
        db = postgres_session_factory()
        try:
            actor = db.get(User, coordinator_id)
            barrier.wait(timeout=10)
            session = coordination_service.create_regular_session(
                db,
                actor,
                WS,
                availability_entry_id=entry_id,
                capacity=3,
            )
            db.commit()
            return ("ok", session.id)
        except coordination_service.CoordinationError as exc:
            db.rollback()
            return ("error", exc.code)
        except Exception as exc:  # pragma: no cover - diagnóstico
            db.rollback()
            return ("unexpected", repr(exc))
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, entry_ids))

    assert sorted(result[0] for result in results) == ["error", "ok"], results
    errors = [result for result in results if result[0] == "error"]
    assert errors[0][1] == "location_conflict", results
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 1


def test_non_availability_integrity_error_is_not_classified_as_duplicate(
    postgres_db: Session, monkeypatch
) -> None:
    """Somente a unicidade da oferta vira `entry_already_converted`."""
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db,
        instructor,
        entries=[
            {
                "kind": "available",
                "starts_at": _dt(WS, 14),
                "ends_at": _dt(WS, 15),
                "location_id": location.id,
                "note": None,
            }
        ],
    )

    def broken_flush(*_args, **_kwargs):
        raise IntegrityError(
            "INSERT INTO reiki_sessions ...",
            {},
            Exception(
                'violates foreign key constraint "fk_reiki_sessions_location_id"'
            ),
        )

    monkeypatch.setattr(postgres_db, "flush", broken_flush)
    with pytest.raises(IntegrityError) as exc_info:
        coordination_service.create_regular_session(
            postgres_db,
            coordinator,
            WS,
            availability_entry_id=submission.entries[0].id,
            capacity=3,
        )
    postgres_db.rollback()
    monkeypatch.undo()

    assert not coordination_service._is_availability_entry_unique_violation(
        exc_info.value
    )
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id) is not None
    assert not postgres_db.scalars(
        select(ReikiSession).where(
            ReikiSession.availability_entry_id == submission.entries[0].id
        )
    ).all()
    assert postgres_db.get(
        AvailabilityEntry, submission.entries[0].id
    ) is not None




# ----------------------------- Concorrência: open_enrollment vs operações individuais --------------------------------



@pytest.mark.postgres_pending
def test_open_enrollment_concurrent_with_create_enrollment_no_deadlock(
    postgres_db: Session, postgres_session_factory
):
    # open_enrollment e create_enrollment concorrentes não causam deadlock e respeitam a fase do ciclo
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, 'Ministrante')
    session = _make_session(postgres_db, cycle, instructor=instructor, status=SessionStatus.SCHEDULED)
    participant = _make_user(postgres_db, Role.PARTICIPANT, 'Participante')
    postgres_db.commit()

    barrier = Barrier(2)
    results: dict[str, tuple[str, object]] = {}

    def open_enrollment_attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            locked = phase2_service.open_enrollment(db, WS)
            db.commit()
            return ('ok', locked.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ('error', exc.code)
        finally:
            db.close()

    def create_enrollment_attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            user = db.get(User, participant.id)
            enrollment = phase2_service.create_enrollment(db, user, session.id)
            db.commit()
            return ('ok', enrollment.status.value)
        except phase2_service.EnrollmentError as exc:
            db.rollback()
            return ('error', exc.code)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(open_enrollment_attempt), pool.submit(create_enrollment_attempt)]
        results_list = [f.result(timeout=30) for f in futures]

    assert len(results_list) == 2
    assert all(not isinstance(r, Exception) for r in results_list)

    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == CyclePhase.ENROLLMENT_OPEN

    enrollments = postgres_db.scalars(
        select(Enrollment).where(Enrollment.session_id == session.id)
    ).all()
    successful_enrolls = [r for r in results_list if r[0] == 'ok' and r[1] == 'confirmed']
    if successful_enrolls:
        assert len(enrollments) >= 1
        assert any(e.status == EnrollmentStatus.CONFIRMED for e in enrollments)




@pytest.mark.postgres_pending
def test_open_enrollment_concurrent_with_open_session_no_deadlock(
    postgres_db: Session, postgres_session_factory
):
    # open_enrollment e open_session concorrentes não causam deadlock e respeitam a fase do ciclo
    cycle = _make_cycle(postgres_db, phase=CyclePhase.ENROLLMENT_PENDING)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, 'Ministrante')
    session = _make_session(postgres_db, cycle, instructor=instructor, status=SessionStatus.SCHEDULED)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, 'Coordenação')
    postgres_db.commit()

    barrier = Barrier(2)
    results: dict[str, tuple[str, object]] = {}

    def open_enrollment_attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            locked = phase2_service.open_enrollment(db, WS)
            db.commit()
            return ('ok', locked.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ('error', exc.code)
        finally:
            db.close()

    def open_session_attempt():
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            user = db.get(User, coordinator.id)
            opened = phase4_service.open_session(db, user, session.id)
            db.commit()
            return ('ok', opened.status.value)
        except phase4_service.ReallocationError as exc:
            db.rollback()
            return ('error', exc.code)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(open_enrollment_attempt), pool.submit(open_session_attempt)]
        results_list = [f.result(timeout=30) for f in futures]

    assert len(results_list) == 2
    assert all(not isinstance(r, Exception) for r in results_list)

    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == CyclePhase.ENROLLMENT_OPEN