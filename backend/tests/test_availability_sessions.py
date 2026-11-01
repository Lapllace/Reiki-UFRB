"""Disponibilidades administrativas e sessões regulares (Etapa B, Sprint 2).

Cobre a consulta de disponibilidades da semana e a criação de sessões
regulares a partir de uma oferta, com PostgreSQL real (bloqueios, índice
único e sobreposição de intervalos não são validados no SQLite).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier, Event, Thread, current_thread
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.location import Location
from app.models.phase2 import (
    AvailabilityEntry,
    AvailabilityEntryKind,
    AvailabilityStatus,
    WeeklyAvailability,
)
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User
from app.services import coordination_service, phase2_service, schedule_service
from tests.conftest import login
from tests.test_auth import PASSWORD

# 2026-11-09 é segunda-feira; 2026-11-11 é quarta; 2026-11-15 é domingo.
WS = date(2026, 11, 9)
NEXT_WS = WS + timedelta(days=7)

# Estes testes exigem o PostgreSQL real (mesma infraestrutura dos demais).
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


def _make_location(db: Session, *, active: bool = True) -> Location:
    location = Location(
        name=f"Local {uuid.uuid4().hex[:8]}",
        is_active=active,
    )
    db.add(location)
    db.commit()
    return location


BAHIA = ZoneInfo("America/Bahia")


def _dt(day: date, hour: int = 14, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _local_dt(day: date, hour: int = 14, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BAHIA)


def _entries(
    count: int,
    *,
    day: date = WS,
    location: Location | None = None,
    note: str | None = None,
) -> list[dict]:
    base = _dt(day)
    return [
        {
            "kind": "available",
            "starts_at": base + timedelta(days=i),
            "ends_at": base + timedelta(days=i, hours=1),
            "location_id": location.id if location else None,
            "note": note,
        }
        for i in range(count)
    ]


def _submit(
    db: Session,
    instructor: User,
    *,
    week_start: date = WS,
    unavailable: bool = False,
    entries: list[dict] | None = None,
    note: str | None = None,
) -> WeeklyAvailability:
    submission = phase2_service.submit_availability(
        db,
        instructor,
        week_start,
        unavailable=unavailable,
        entries=[] if unavailable else (entries or _entries(1, day=week_start)),
        note=note,
    )
    db.commit()
    return submission


def _post_session(
    client: TestClient,
    entry_id,
    *,
    capacity: int = 6,
    location_id=None,
    week_start: date = WS,
):
    body: dict = {
        "availabilityEntryId": str(entry_id),
        "capacity": capacity,
    }
    if location_id is not None:
        body["locationId"] = str(location_id)
    return client.post(
        f"/coordination/cycles/{week_start.isoformat()}/sessions", json=body
    )


def _admin_session(
    db: Session,
    *,
    instructor: User,
    location: Location,
    starts_at: datetime,
    ends_at: datetime,
    status: SessionStatus = SessionStatus.SCHEDULED,
    cycle: WeeklyCycle | None = None,
) -> ReikiSession:
    session = ReikiSession(
        cycle_id=cycle.id if cycle else None,
        instructor_id=instructor.id,
        location_id=location.id,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=4,
        status=status,
        is_extra=False,
    )
    db.add(session)
    db.commit()
    return session


def _rows_by_instructor(body: dict) -> dict[str, dict]:
    return {row["instructorId"]: row for row in body["instructors"]}


def _current_entry(submission: WeeklyAvailability) -> AvailabilityEntry:
    current = [entry for entry in submission.entries if entry.is_current]
    assert len(current) == 1
    return current[0]


# ------------------------- Consulta administrativa -------------------------


def test_get_availabilities_reports_real_state_of_active_instructors(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    location = _make_location(postgres_db)
    submitted = _make_user(postgres_db, Role.INSTRUCTOR, "Ofertou")
    unavailable = _make_user(postgres_db, Role.INSTRUCTOR, "Indisponível")
    pending = _make_user(postgres_db, Role.INSTRUCTOR, "Sem submissão")
    inactive = _make_user(
        postgres_db, Role.INSTRUCTOR, "Inativo", active=False
    )

    offered_at = _dt(WS, 14)
    offer_entries = [
        {
            "kind": "available",
            "starts_at": offered_at,
            "ends_at": offered_at + timedelta(hours=1),
            "location_id": location.id,
            "note": "Sala preferida",
        },
        {
            "kind": "available",
            "starts_at": _dt(WS + timedelta(days=2), 9),
            "ends_at": _dt(WS + timedelta(days=2), 10),
            "location_id": None,
            "note": None,
        },
    ]
    submission = _submit(
        postgres_db,
        submitted,
        entries=offer_entries,
        note="Disponível à tarde",
    )
    unavailable_submission = _submit(
        postgres_db, unavailable, unavailable=True, note="Viagem"
    )
    login(postgres_client, coordinator.email, PASSWORD)

    # Domingo é normalizado para a segunda-feira da mesma semana.
    sunday = WS + timedelta(days=6)
    response = postgres_client.get(
        f"/coordination/cycles/{sunday.isoformat()}/availabilities"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weekStart"] == WS.isoformat()
    assert body["weekEnd"] == (WS + timedelta(days=6)).isoformat()
    assert body["cycleId"] == str(cycle.id)
    assert body["cyclePhase"] == CyclePhase.COLLECTING_AVAILABILITY.value
    rows = _rows_by_instructor(body)
    assert set(rows) == {
        str(submitted.id),
        str(unavailable.id),
        str(pending.id),
    }
    assert str(inactive.id) not in rows

    offered = rows[str(submitted.id)]
    assert offered["availabilityId"] == str(submission.id)
    assert offered["status"] == AvailabilityStatus.SUBMITTED.value
    assert offered["note"] == "Disponível à tarde"
    assert datetime.fromisoformat(
        offered["submittedAt"].replace("Z", "+00:00")
    ) == submission.submitted_at.astimezone(UTC)
    assert len(offered["entries"]) == 2
    first, second = offered["entries"]
    assert first["id"]
    assert first["kind"] == AvailabilityEntryKind.AVAILABLE.value
    assert datetime.fromisoformat(
        first["startsAt"].replace("Z", "+00:00")
    ) == offered_at
    assert datetime.fromisoformat(
        first["endsAt"].replace("Z", "+00:00")
    ) == offered_at + timedelta(hours=1)
    assert first["location"]["id"] == str(location.id)
    assert first["note"] == "Sala preferida"
    assert first["convertedSessionId"] is None
    assert second["location"] is None

    declared = rows[str(unavailable.id)]
    assert declared["availabilityId"] == str(unavailable_submission.id)
    assert declared["status"] == AvailabilityStatus.UNAVAILABLE.value
    assert declared["note"] == "Viagem"
    assert declared["submittedAt"] is not None
    assert declared["entries"] == []

    absent = rows[str(pending.id)]
    assert absent["availabilityId"] is None
    assert absent["status"] == AvailabilityStatus.PENDING.value
    assert absent["submittedAt"] is None
    assert absent["entries"] == []


def test_get_availabilities_without_cycle_lists_all_instructors_as_pending(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cycleId"] is None
    assert body["cyclePhase"] is None
    row = _rows_by_instructor(body)[str(instructor.id)]
    assert row["status"] == AvailabilityStatus.PENDING.value
    assert row["entries"] == []


# -------------------------- Criação de sessões ----------------------------


def test_create_session_uses_offer_data_and_does_not_publish_agenda(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    entry = _entries(1, location=location, note="Oferta")[0]
    submission = _submit(postgres_db, instructor, entries=[entry])
    stored_entry = submission.entries[0]
    login(postgres_client, coordinator.email, PASSWORD)

    # Domingo normaliza para a mesma semana.
    response = _post_session(
        postgres_client,
        stored_entry.id,
        capacity=7,
        week_start=WS + timedelta(days=6),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert datetime.fromisoformat(
        body["startsAt"].replace("Z", "+00:00")
    ) == stored_entry.starts_at.astimezone(UTC)
    assert datetime.fromisoformat(
        body["endsAt"].replace("Z", "+00:00")
    ) == stored_entry.ends_at.astimezone(UTC)
    assert body["status"] == SessionStatus.SCHEDULED.value
    assert body["isExtra"] is False
    assert body["capacity"] == 7
    assert body["location"]["id"] == str(location.id)
    assert body["instructor"]["id"] == str(instructor.id)
    assert body["confirmedCount"] == 0

    postgres_db.expire_all()
    stored = postgres_db.scalar(
        select(ReikiSession).where(
            ReikiSession.availability_entry_id == stored_entry.id
        )
    )
    assert stored is not None
    assert stored.cycle_id == cycle.id
    assert stored.instructor_id == instructor.id
    assert stored.location_id == location.id
    assert stored.created_by == coordinator.id
    assert stored.status == SessionStatus.SCHEDULED
    assert stored.is_extra is False
    assert stored.capacity == 7
    assert stored.starts_at == stored_entry.starts_at
    assert stored.ends_at == stored_entry.ends_at
    assert stored.id == uuid.UUID(body["id"])

    # Criar a sessão não publica a agenda, não abre inscrições nem muda a fase.
    current_cycle = postgres_db.get(WeeklyCycle, cycle.id)
    assert current_cycle.phase == CyclePhase.COLLECTING_AVAILABILITY
    assert schedule_service.is_published(current_cycle) is False
    assert postgres_db.scalar(
        select(func.count())
        .select_from(ReikiSession)
        .where(ReikiSession.cycle_id == cycle.id)
    ) == 1

    # A consulta administrativa passa a indicar a oferta já convertida.
    listed = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    )
    listed_entry = _rows_by_instructor(listed.json())[str(instructor.id)][
        "entries"
    ][0]
    assert listed_entry["convertedSessionId"] == str(stored.id)


def test_create_session_requires_location_when_offer_has_none(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(postgres_db, instructor, entries=_entries(1))
    entry = submission.entries[0]
    login(postgres_client, coordinator.email, PASSWORD)

    rejected = _post_session(postgres_client, entry.id)

    assert rejected.status_code == 422, rejected.text
    assert rejected.headers["X-Error-Code"] == "location_required"
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 0

    accepted = _post_session(
        postgres_client, entry.id, location_id=location.id
    )

    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["location"]["id"] == str(location.id)


def test_create_session_rejects_location_different_from_offer(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    offered_location = _make_location(postgres_db)
    other_location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=offered_location)
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(
        postgres_client,
        submission.entries[0].id,
        location_id=other_location.id,
    )

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "location_mismatch"


def test_create_session_rejects_unknown_or_inactive_location(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    inactive = _make_location(postgres_db, active=False)
    expected = _submit(postgres_db, instructor, entries=_entries(1))
    login(postgres_client, coordinator.email, PASSWORD)

    unknown = _post_session(
        postgres_client, expected.entries[0].id, location_id=uuid.uuid4()
    )
    assert unknown.status_code == 404, unknown.text
    assert unknown.headers["X-Error-Code"] == "location_not_found"

    # Mantém a oferta intacta e usa outro horário para o local inativo.
    second = _submit(
        postgres_db,
        instructor,
        entries=_entries(1, day=WS + timedelta(days=1)),
    )
    blocked = _post_session(
        postgres_client, _current_entry(second).id, location_id=inactive.id
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.headers["X-Error-Code"] == "location_inactive"

    # Oferta que aponta para um local posteriormente inativado.
    offered_location = _make_location(postgres_db)
    third = _submit(
        postgres_db,
        instructor,
        entries=_entries(1, day=WS + timedelta(days=2), location=offered_location),
    )
    offered_location.is_active = False
    postgres_db.commit()
    unavailable_location = _post_session(
        postgres_client, _current_entry(third).id
    )
    assert unavailable_location.status_code == 409, unavailable_location.text
    assert unavailable_location.headers["X-Error-Code"] == "location_inactive"


def test_create_session_requires_existing_cycle(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, uuid.uuid4(), week_start=WS)

    assert response.status_code == 404, response.text
    assert response.headers["X-Error-Code"] == "cycle_not_found"


def test_create_session_requires_existing_offer(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, uuid.uuid4())

    assert response.status_code == 404, response.text
    assert response.headers["X-Error-Code"] == "entry_not_found"


def test_create_session_rejects_offer_from_another_week(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db, WS)
    _make_cycle(postgres_db, NEXT_WS)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    submission = _submit(
        postgres_db, instructor, week_start=NEXT_WS, entries=_entries(1, day=NEXT_WS)
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(
        postgres_client, submission.entries[0].id, week_start=WS
    )

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "entry_not_in_cycle"


def test_create_session_rejects_unavailable_offer(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    submission = _submit(postgres_db, instructor, entries=_entries(1))
    entry = submission.entries[0]
    entry.kind = AvailabilityEntryKind.UNAVAILABLE
    postgres_db.commit()
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry.id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "entry_unavailable"


def test_create_session_rejects_inactive_instructor(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    submission = _submit(postgres_db, instructor, entries=_entries(1))
    instructor.is_active = False
    postgres_db.commit()
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, submission.entries[0].id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "instructor_inactive"


@pytest.mark.parametrize("capacity", [0, -1])
def test_create_session_requires_positive_capacity(
    postgres_client: TestClient, postgres_db: Session, capacity: int
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    submission = _submit(postgres_db, instructor, entries=_entries(1))
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(
        postgres_client, submission.entries[0].id, capacity=capacity
    )

    assert response.status_code == 422, response.text
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 0


# ------------------------ Fase do ciclo -----------------------------------


@pytest.mark.parametrize(
    "phase",
    [
        CyclePhase.ENROLLMENT_PENDING,
        CyclePhase.ENROLLMENT_OPEN,
        CyclePhase.IN_PROGRESS,
        CyclePhase.CLOSED,
    ],
)
def test_create_session_rejected_outside_collecting_phase(
    postgres_client: TestClient,
    postgres_db: Session,
    phase: CyclePhase,
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry_id = submission.entries[0].id
    cycle.phase = phase
    postgres_db.commit()
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry_id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "invalid_cycle_phase"
    postgres_db.expire_all()
    assert postgres_db.get(WeeklyCycle, cycle.id).phase == phase
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 0


def test_create_session_allowed_in_collecting_phase(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db, phase=CyclePhase.COLLECTING_AVAILABILITY)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, submission.entries[0].id)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "phase",
    [
        CyclePhase.ENROLLMENT_PENDING,
        CyclePhase.ENROLLMENT_OPEN,
        CyclePhase.IN_PROGRESS,
        CyclePhase.CLOSED,
    ],
)
def test_resubmission_rejected_after_collecting_phase(
    postgres_db: Session, phase: CyclePhase
) -> None:
    cycle = _make_cycle(postgres_db)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    submission = _submit(
        postgres_db, instructor, entries=_entries(1)
    )
    cycle.phase = phase
    postgres_db.commit()

    with pytest.raises(phase2_service.AvailabilityError) as exc:
        phase2_service.submit_availability(
            postgres_db,
            instructor,
            WS,
            unavailable=False,
            entries=_entries(1, day=WS + timedelta(days=1)),
        )

    assert exc.value.code == "locked"
    postgres_db.expire_all()
    rows = postgres_db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.availability_id == submission.id
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].is_current is True


def test_resubmission_allowed_in_collecting_phase(
    postgres_db: Session,
) -> None:
    _make_cycle(postgres_db, phase=CyclePhase.COLLECTING_AVAILABILITY)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    first = _submit(postgres_db, instructor, entries=_entries(1))

    second = phase2_service.submit_availability(
        postgres_db,
        instructor,
        WS,
        unavailable=False,
        entries=_entries(1, day=WS + timedelta(days=1)),
    )

    assert second.id == first.id
    current = [entry for entry in second.entries if entry.is_current]
    assert len(current) == 1


# ---------------------- Limites temporais da semana -----------------------


@pytest.mark.parametrize(
    "case,starts_at,ends_at,expected_code",
    [
        pytest.param(
            "monday",
            _local_dt(WS, 9),
            _local_dt(WS, 10),
            None,
            id="oferta-valida-segunda",
        ),
        pytest.param(
            "sunday",
            _local_dt(WS + timedelta(days=6), 20),
            _local_dt(WS + timedelta(days=6), 21),
            None,
            id="oferta-valida-domingo",
        ),
        pytest.param(
            "before_week",
            _local_dt(WS - timedelta(days=1), 23),
            _local_dt(WS - timedelta(days=1), 23, 59),
            "outside_week",
            id="comeca-antes-da-semana",
        ),
        pytest.param(
            "after_week",
            _local_dt(WS + timedelta(days=6), 23, 30),
            _local_dt(WS + timedelta(days=7), 0, 30),
            "outside_week",
            id="termina-depois-da-semana",
        ),
        pytest.param(
            "crosses_boundary",
            _local_dt(WS + timedelta(days=6), 23),
            _local_dt(WS + timedelta(days=7), 1),
            "outside_week",
            id="atravessa-limite-entre-semanas",
        ),
        pytest.param(
            "ends_at_upper_bound",
            _local_dt(WS + timedelta(days=6), 23),
            _local_dt(WS + timedelta(days=7), 0),
            None,
            id="termina-exatamente-no-limite",
        ),
        pytest.param(
            "starts_at_upper_bound",
            _local_dt(WS + timedelta(days=7), 0),
            _local_dt(WS + timedelta(days=7), 1),
            "outside_week",
            id="comeca-no-limite-superior",
        ),
    ],
)
def test_submit_availability_enforces_institutional_week_bounds(
    postgres_db: Session,
    case: str,
    starts_at: datetime,
    ends_at: datetime,
    expected_code: str | None,
) -> None:
    _make_cycle(postgres_db)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    entries = [
        {
            "kind": "available",
            "starts_at": starts_at,
            "ends_at": ends_at,
            "location_id": None,
            "note": None,
        }
    ]

    if expected_code is None:
        submission = phase2_service.submit_availability(
            postgres_db,
            instructor,
            WS,
            unavailable=False,
            entries=entries,
        )
        assert len(submission.entries) == 1
        return

    with pytest.raises(phase2_service.AvailabilityError) as exc:
        phase2_service.submit_availability(
            postgres_db,
            instructor,
            WS,
            unavailable=False,
            entries=entries,
        )
    assert exc.value.code == expected_code
    assert postgres_db.scalar(
        select(func.count()).select_from(WeeklyAvailability)
    ) == 0


def test_create_session_revalidates_week_bounds_on_conversion(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    """Oferta gravada fora da semana não pode ser convertida."""
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    availability = WeeklyAvailability(
        cycle_id=cycle.id,
        instructor_id=instructor.id,
        status=AvailabilityStatus.SUBMITTED,
        submitted_at=datetime.now(UTC),
    )
    postgres_db.add(availability)
    postgres_db.flush()
    entry = AvailabilityEntry(
        availability_id=availability.id,
        kind=AvailabilityEntryKind.AVAILABLE,
        starts_at=_local_dt(WS + timedelta(days=7), 1),
        ends_at=_local_dt(WS + timedelta(days=7), 2),
        location_id=location.id,
        is_current=True,
    )
    postgres_db.add(entry)
    postgres_db.commit()
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry.id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "outside_week"
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 0


# --------------------------- Duplicidade ----------------------------------


def test_create_session_rejects_duplicate_conversion(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry = submission.entries[0]
    login(postgres_client, coordinator.email, PASSWORD)

    first = _post_session(postgres_client, entry.id)
    second = _post_session(postgres_client, entry.id)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.headers["X-Error-Code"] == "entry_already_converted"
    assert postgres_db.scalar(
        select(func.count())
        .select_from(ReikiSession)
        .where(ReikiSession.availability_entry_id == entry.id)
    ) == 1


def test_concurrent_conversion_creates_single_session(
    postgres_db: Session, postgres_session_factory
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry_id = submission.entries[0].id
    coordinator_id = coordinator.id
    barrier = Barrier(2)

    def attempt(_):
        db = postgres_session_factory()
        try:
            actor = db.get(User, coordinator_id)
            barrier.wait(timeout=10)
            session = coordination_service.create_regular_session(
                db,
                actor,
                WS,
                availability_entry_id=entry_id,
                capacity=5,
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
        results = list(pool.map(attempt, range(2)))

    statuses = sorted(result[0] for result in results)
    assert statuses == ["error", "ok"], results
    errors = [result for result in results if result[0] == "error"]
    assert errors[0][1] == "entry_already_converted"
    count = postgres_db.scalar(
        select(func.count())
        .select_from(ReikiSession)
        .where(ReikiSession.availability_entry_id == entry_id)
    )
    assert count == 1


# ---------------------------- Conflitos -----------------------------------


def test_create_session_rejects_instructor_conflict(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    cycle = _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    offer_location = _make_location(postgres_db)
    other_location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=offer_location)
    )
    entry = submission.entries[0]
    _admin_session(
        postgres_db,
        instructor=instructor,
        location=other_location,
        starts_at=entry.starts_at - timedelta(minutes=30),
        ends_at=entry.starts_at + timedelta(minutes=30),
        cycle=cycle,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry.id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "instructor_conflict"


def test_create_session_allows_touching_but_not_overlapping_periods(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry = submission.entries[0]
    # Termina exatamente quando a oferta começa: não há sobreposição.
    _admin_session(
        postgres_db,
        instructor=instructor,
        location=location,
        starts_at=entry.starts_at - timedelta(hours=1),
        ends_at=entry.starts_at,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry.id)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "status", [SessionStatus.CANCELLED, SessionStatus.COMPLETED]
)
def test_create_session_ignores_inactive_sessions_in_conflicts(
    postgres_client: TestClient,
    postgres_db: Session,
    status: SessionStatus,
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry = submission.entries[0]
    _admin_session(
        postgres_db,
        instructor=instructor,
        location=location,
        starts_at=entry.starts_at,
        ends_at=entry.ends_at,
        status=status,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry.id)

    assert response.status_code == 201, response.text


def test_create_session_rejects_location_conflict(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    other_instructor = _make_user(
        postgres_db, Role.INSTRUCTOR, "Outro ministrante"
    )
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry = submission.entries[0]
    _admin_session(
        postgres_db,
        instructor=other_instructor,
        location=location,
        starts_at=entry.starts_at,
        ends_at=entry.ends_at,
        status=SessionStatus.OPEN,
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, entry.id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "location_conflict"


# -------------------- Autorização e proteção de origem --------------------


def test_availabilities_require_coordinator(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")

    unauthenticated = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    )
    assert unauthenticated.status_code == 401

    login(postgres_client, participant.email, PASSWORD)
    assert postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    ).status_code == 403

    postgres_client.post("/auth/logout")
    login(postgres_client, instructor.email, PASSWORD)
    assert postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    ).status_code == 403


def test_create_session_requires_coordinator_and_same_origin(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    participant = _make_user(postgres_db, Role.PARTICIPANT, "Participante")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry_id = submission.entries[0].id

    assert _post_session(postgres_client, entry_id).status_code == 401

    login(postgres_client, participant.email, PASSWORD)
    assert _post_session(postgres_client, entry_id).status_code == 403

    postgres_client.post("/auth/logout")
    login(postgres_client, instructor.email, PASSWORD)
    assert _post_session(postgres_client, entry_id).status_code == 403

    postgres_client.post("/auth/logout")
    login(postgres_client, coordinator.email, PASSWORD)
    blocked = postgres_client.post(
        f"/coordination/cycles/{WS.isoformat()}/sessions",
        json={"availabilityEntryId": str(entry_id), "capacity": 5},
        headers={"Origin": "http://evil.example"},
    )
    assert blocked.status_code == 403, blocked.text

    allowed = postgres_client.post(
        f"/coordination/cycles/{WS.isoformat()}/sessions",
        json={"availabilityEntryId": str(entry_id), "capacity": 5},
        headers={"Origin": "http://localhost:3000"},
    )
    assert allowed.status_code == 201, allowed.text


def test_resubmission_preserves_history_and_original_offer_link(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    """Reenviar mantém a oferta antiga e o vínculo da sessão já convertida."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    old_entry_id = submission.entries[0].id
    login(postgres_client, coordinator.email, PASSWORD)

    created = _post_session(postgres_client, old_entry_id)
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    # Reenvio pelo mesmo ministrante na mesma semana: a oferta antiga vira
    # histórico, mas continua vinculada à sessão já criada.
    replacement = _entries(
        1, day=WS + timedelta(days=3), location=location
    )
    _submit(postgres_db, instructor, entries=replacement)

    postgres_db.expire_all()
    session = postgres_db.get(ReikiSession, uuid.UUID(session_id))
    assert session is not None
    assert session.availability_entry_id == old_entry_id
    assert session.instructor_id == instructor.id

    old_entry = postgres_db.get(AvailabilityEntry, old_entry_id)
    assert old_entry is not None
    assert old_entry.is_current is False
    current_entries = postgres_db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.availability_id == submission.id,
            AvailabilityEntry.is_current.is_(True),
        )
    ).all()
    assert len(current_entries) == 1
    new_entry = current_entries[0]
    assert new_entry.id != old_entry_id

    # O resumo conta somente a oferta vigente.
    cycle_body = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}"
    ).json()
    assert _rows_by_instructor(cycle_body)[str(instructor.id)][
        "sessionsOffered"
    ] == 1

    # A consulta administrativa expõe as duas entradas e identifica a antiga.
    admin_body = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    ).json()
    admin_entries = {
        entry["id"]: entry
        for entry in _rows_by_instructor(admin_body)[str(instructor.id)][
            "entries"
        ]
    }
    assert len(admin_entries) == 2
    assert admin_entries[str(old_entry_id)]["isCurrent"] is False
    assert admin_entries[str(old_entry_id)]["convertedSessionId"] == session_id
    assert admin_entries[str(new_entry.id)]["isCurrent"] is True
    assert admin_entries[str(new_entry.id)]["convertedSessionId"] is None

    # A oferta histórica não pode ser convertida de novo.
    repeated = _post_session(postgres_client, old_entry_id)
    assert repeated.status_code == 409, repeated.text
    assert repeated.headers["X-Error-Code"] == "entry_already_converted"

    # A oferta vigente continua conversível e usa exatamente o horário ofertado.
    accepted = _post_session(postgres_client, new_entry.id)
    assert accepted.status_code == 201, accepted.text
    assert datetime.fromisoformat(
        accepted.json()["startsAt"].replace("Z", "+00:00")
    ) == new_entry.starts_at.astimezone(UTC)

    # A API do ministrante mostra somente a oferta vigente.
    postgres_client.post("/auth/logout")
    login(postgres_client, instructor.email, PASSWORD)
    mine = postgres_client.get(
        "/instructor/availability", params={"weekStart": WS.isoformat()}
    )
    assert mine.status_code == 200, mine.text
    mine_entries = mine.json()["entries"]
    assert [entry["id"] for entry in mine_entries] == [str(new_entry.id)]


def test_plain_resubmission_marks_previous_entries_as_history(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    """Reenvio normal preserva as ofertas antigas como não vigentes."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    first = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    old_entry_id = first.entries[0].id
    second = _submit(
        postgres_db,
        instructor,
        entries=_entries(1, day=WS + timedelta(days=1), location=location),
    )
    new_entry_id = second.entries[-1].id

    postgres_db.expire_all()
    rows = postgres_db.scalars(
        select(AvailabilityEntry)
        .where(AvailabilityEntry.availability_id == first.id)
        .order_by(AvailabilityEntry.starts_at)
    ).all()
    assert len(rows) == 2
    assert {row.id: row.is_current for row in rows} == {
        old_entry_id: False,
        new_entry_id: True,
    }

    login(postgres_client, coordinator.email, PASSWORD)
    cycle_body = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}"
    ).json()
    assert _rows_by_instructor(cycle_body)[str(instructor.id)][
        "sessionsOffered"
    ] == 1

    admin_body = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    ).json()
    admin_entries = _rows_by_instructor(admin_body)[str(instructor.id)][
        "entries"
    ]
    assert {entry["id"]: entry["isCurrent"] for entry in admin_entries} == {
        str(old_entry_id): False,
        str(new_entry_id): True,
    }

    postgres_client.post("/auth/logout")
    login(postgres_client, instructor.email, PASSWORD)
    mine = postgres_client.get(
        "/instructor/availability", params={"weekStart": WS.isoformat()}
    ).json()
    assert [entry["id"] for entry in mine["entries"]] == [str(new_entry_id)]


def test_historical_unconverted_offer_cannot_be_converted(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    first = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    old_entry_id = first.entries[0].id
    _submit(
        postgres_db,
        instructor,
        entries=_entries(1, day=WS + timedelta(days=1), location=location),
    )
    login(postgres_client, coordinator.email, PASSWORD)

    response = _post_session(postgres_client, old_entry_id)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "entry_not_current"
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 0


def test_declaring_unavailability_preserves_previous_history(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    """Declarar indisponibilidade também não apaga as ofertas anteriores."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    first = _submit(
        postgres_db, instructor, entries=_entries(2, location=location)
    )
    old_ids = {entry.id for entry in first.entries}

    declared = _submit(
        postgres_db, instructor, unavailable=True, note="Viagem"
    )
    assert declared.status == AvailabilityStatus.UNAVAILABLE

    postgres_db.expire_all()
    rows = postgres_db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.availability_id == first.id
        )
    ).all()
    assert {row.id for row in rows} == old_ids
    assert all(row.is_current is False for row in rows)

    login(postgres_client, coordinator.email, PASSWORD)
    cycle_body = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}"
    ).json()
    assert _rows_by_instructor(cycle_body)[str(instructor.id)][
        "sessionsOffered"
    ] == 0
    admin_body = postgres_client.get(
        f"/coordination/cycles/{WS.isoformat()}/availabilities"
    ).json()
    admin_entries = _rows_by_instructor(admin_body)[str(instructor.id)][
        "entries"
    ]
    assert len(admin_entries) == 2
    assert all(entry["isCurrent"] is False for entry in admin_entries)

    postgres_client.post("/auth/logout")
    login(postgres_client, instructor.email, PASSWORD)
    mine = postgres_client.get(
        "/instructor/availability", params={"weekStart": WS.isoformat()}
    ).json()
    assert mine["status"] == AvailabilityStatus.UNAVAILABLE.value
    assert mine["entries"] == []


# ------------- Concorrência: o ciclo é o primeiro bloqueio -------------


def test_publication_waits_for_creation_and_sees_the_created_session(
    postgres_db: Session, postgres_session_factory, monkeypatch
) -> None:
    """Criação primeiro: a publicação espera e enxerga a sessão criada."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry_id = submission.entries[0].id
    coordinator_id = coordinator.id

    creation_holds_cycle = Event()
    publisher_started = Event()
    barrier = Barrier(2)
    original_lock = coordination_service.lock_cycle

    def creation_lock(db: Session, week_start: date):
        cycle = original_lock(db, week_start)
        # A criação mantém o ciclo bloqueado até a publicação iniciar, o que
        # garante que a publicação tente o lock enquanto a sessão é criada.
        creation_holds_cycle.set()
        assert publisher_started.wait(timeout=10), "publicação não iniciou"
        return cycle

    monkeypatch.setattr(coordination_service, "lock_cycle", creation_lock)

    # Registra o que a publicação viu ao validar as sessões do ciclo.
    seen_sessions: list[uuid.UUID] = []
    original_validate = phase2_service._validate_session_periods

    def recording_validate(sessions, week_start: date) -> None:
        seen_sessions.extend(row.id for row in sessions)
        original_validate(sessions, week_start)

    monkeypatch.setattr(
        phase2_service, "_validate_session_periods", recording_validate
    )

    def create() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            actor = db.get(User, coordinator_id)
            session = coordination_service.create_regular_session(
                db,
                actor,
                WS,
                availability_entry_id=entry_id,
                capacity=4,
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

    def publish() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            assert creation_holds_cycle.wait(timeout=10), "criação não iniciou"
            publisher_started.set()
            cycle = phase2_service.publish_week(db, WS)
            db.commit()
            return ("ok", cycle.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        except Exception as exc:  # pragma: no cover - diagnóstico
            db.rollback()
            return ("unexpected", repr(exc))
        finally:
            db.close()

    results: dict[str, tuple[str, object]] = {}
    create_thread = Thread(target=lambda: results.update(create=create()))
    publish_thread = Thread(target=lambda: results.update(publish=publish()))
    create_thread.start()
    publish_thread.start()
    create_thread.join(timeout=30)
    publish_thread.join(timeout=30)
    assert not create_thread.is_alive()
    assert not publish_thread.is_alive()

    created = results["create"]
    published = results["publish"]
    assert created[0] == "ok", created
    assert published == ("ok", CyclePhase.ENROLLMENT_PENDING.value), published
    assert created[1] in seen_sessions

    postgres_db.expire_all()
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    session_row = postgres_db.get(ReikiSession, created[1])
    assert cycle is not None
    assert cycle.phase == CyclePhase.ENROLLMENT_PENDING
    assert session_row is not None
    assert session_row.cycle_id == cycle.id


def test_creation_after_publication_is_rejected_without_orphan_session(
    postgres_db: Session, postgres_session_factory, monkeypatch
) -> None:
    """Publicação primeiro: a criação posterior falha e não deixa sessão órfã."""
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    submission = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    entry_id = submission.entries[0].id
    coordinator_id = coordinator.id

    publication_holds_cycle = Event()
    creator_started = Event()
    original_lock = schedule_service.lock_cycle

    def publication_lock(db: Session, week_start: date):
        cycle = original_lock(db, week_start)
        if current_thread().name == "publisher":
            publication_holds_cycle.set()
            assert creator_started.wait(timeout=10), "criação não iniciou"
        return cycle

    monkeypatch.setattr(schedule_service, "lock_cycle", publication_lock)

    def publish() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            cycle = phase2_service.publish_week(db, WS)
            db.commit()
            return ("ok", cycle.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    def create() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            assert publication_holds_cycle.wait(timeout=10), "publicação não iniciou"
            creator_started.set()
            actor = db.get(User, coordinator_id)
            session = coordination_service.create_regular_session(
                db,
                actor,
                WS,
                availability_entry_id=entry_id,
                capacity=4,
            )
            db.commit()
            return ("ok", session.id)
        except coordination_service.CoordinationError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    results: dict[str, tuple[str, object]] = {}
    publish_thread = Thread(
        target=lambda: results.update(publish=publish()), name="publisher"
    )
    create_thread = Thread(target=lambda: results.update(create=create()))
    publish_thread.start()
    create_thread.start()
    publish_thread.join(timeout=30)
    create_thread.join(timeout=30)
    assert not publish_thread.is_alive()
    assert not create_thread.is_alive()

    published = results["publish"]
    created = results["create"]
    assert published == ("ok", CyclePhase.ENROLLMENT_PENDING.value), published
    assert created == ("error", "invalid_cycle_phase"), created

    postgres_db.expire_all()
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    assert cycle is not None
    assert cycle.phase == CyclePhase.ENROLLMENT_PENDING
    # Nenhuma sessão foi criada fora da agenda já publicada.
    assert postgres_db.scalar(
        select(func.count()).select_from(ReikiSession)
    ) == 0


def test_publication_waits_for_concurrent_resubmission(
    postgres_db: Session, postgres_session_factory, monkeypatch
) -> None:
    """Reenvio primeiro: a publicação espera e publica a oferta mais recente."""
    _make_cycle(postgres_db)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    first = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    old_entry_id = first.entries[0].id
    instructor_id = instructor.id
    replacement = _entries(
        1, day=WS + timedelta(days=2), location=location
    )
    replacement_starts = replacement[0]["starts_at"]

    resubmission_holds_cycle = Event()
    publisher_started = Event()
    original_lock = schedule_service.lock_cycle

    def resubmission_lock(db: Session, week_start: date):
        cycle = original_lock(db, week_start)
        if current_thread().name == "resubmitter":
            resubmission_holds_cycle.set()
            assert publisher_started.wait(timeout=10), "publicação não iniciou"
        return cycle

    monkeypatch.setattr(schedule_service, "lock_cycle", resubmission_lock)

    def resubmit() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            actor = db.get(User, instructor_id)
            availability = phase2_service.submit_availability(
                db,
                actor,
                WS,
                unavailable=False,
                entries=replacement,
            )
            db.commit()
            return ("ok", availability.id)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    def publish() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            assert resubmission_holds_cycle.wait(timeout=10), "reenvio não iniciou"
            publisher_started.set()
            cycle = phase2_service.publish_week(db, WS)
            db.commit()
            return ("ok", cycle.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    results: dict[str, tuple[str, object]] = {}
    resubmit_thread = Thread(
        target=lambda: results.update(resubmit=resubmit()), name="resubmitter"
    )
    publish_thread = Thread(
        target=lambda: results.update(publish=publish()), name="publisher"
    )
    resubmit_thread.start()
    publish_thread.start()
    resubmit_thread.join(timeout=30)
    publish_thread.join(timeout=30)
    assert not resubmit_thread.is_alive()
    assert not publish_thread.is_alive()

    assert results["resubmit"][0] == "ok", results["resubmit"]
    assert results["publish"] == (
        "ok",
        CyclePhase.ENROLLMENT_PENDING.value,
    ), results["publish"]

    postgres_db.expire_all()
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    old_entry = postgres_db.get(AvailabilityEntry, old_entry_id)
    current = postgres_db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.availability_id == first.id,
            AvailabilityEntry.is_current.is_(True),
        )
    ).all()
    assert cycle is not None
    assert cycle.phase == CyclePhase.ENROLLMENT_PENDING
    assert old_entry is not None
    assert old_entry.is_current is False
    assert len(current) == 1
    assert current[0].starts_at == replacement_starts


def test_resubmission_after_publication_is_rejected(
    postgres_db: Session, postgres_session_factory, monkeypatch
) -> None:
    """Publicação primeiro: o reenvio posterior é rejeitado e não altera ofertas."""
    _make_cycle(postgres_db)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    first = _submit(
        postgres_db, instructor, entries=_entries(1, location=location)
    )
    old_entry_id = first.entries[0].id
    instructor_id = instructor.id
    replacement = _entries(
        1, day=WS + timedelta(days=2), location=location
    )

    publication_holds_cycle = Event()
    resubmitter_started = Event()
    original_lock = schedule_service.lock_cycle

    def publication_lock(db: Session, week_start: date):
        cycle = original_lock(db, week_start)
        if current_thread().name == "publisher":
            publication_holds_cycle.set()
            assert resubmitter_started.wait(timeout=10), "reenvio não iniciou"
        return cycle

    monkeypatch.setattr(schedule_service, "lock_cycle", publication_lock)

    def publish() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            cycle = phase2_service.publish_week(db, WS)
            db.commit()
            return ("ok", cycle.phase.value)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    def resubmit() -> tuple[str, object]:
        db = postgres_session_factory()
        try:
            assert publication_holds_cycle.wait(timeout=10), "publicação não iniciou"
            resubmitter_started.set()
            actor = db.get(User, instructor_id)
            phase2_service.submit_availability(
                db,
                actor,
                WS,
                unavailable=False,
                entries=replacement,
            )
            db.commit()
            return ("ok", None)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            return ("error", exc.code)
        finally:
            db.close()

    results: dict[str, tuple[str, object]] = {}
    publish_thread = Thread(
        target=lambda: results.update(publish=publish()), name="publisher"
    )
    resubmit_thread = Thread(
        target=lambda: results.update(resubmit=resubmit()), name="resubmitter"
    )
    publish_thread.start()
    resubmit_thread.start()
    publish_thread.join(timeout=30)
    resubmit_thread.join(timeout=30)
    assert not publish_thread.is_alive()
    assert not resubmit_thread.is_alive()

    assert results["publish"] == (
        "ok",
        CyclePhase.ENROLLMENT_PENDING.value,
    ), results["publish"]
    assert results["resubmit"] == ("error", "locked"), results["resubmit"]

    postgres_db.expire_all()
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    old_entry = postgres_db.get(AvailabilityEntry, old_entry_id)
    rows = postgres_db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.availability_id == first.id
        )
    ).all()
    assert cycle is not None
    assert cycle.phase == CyclePhase.ENROLLMENT_PENDING
    assert old_entry is not None
    assert old_entry.is_current is True
    # O reenvio rejeitado não criou uma nova geração.
    assert len(rows) == 1
    assert [row.is_current for row in rows] == [True]


def test_concurrent_submissions_leave_single_current_generation(
    postgres_db: Session, postgres_session_factory
) -> None:
    """Duas submissões simultâneas do mesmo ministrante: uma geração vigente."""
    _make_cycle(postgres_db)
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    location = _make_location(postgres_db)
    instructor_id = instructor.id
    offers = {
        "a": _entries(2, day=WS, location=location),
        "b": _entries(2, day=WS + timedelta(days=3), location=location),
    }
    expected_starts = {
        label: sorted(entry["starts_at"] for entry in entries)
        for label, entries in offers.items()
    }
    barrier = Barrier(2)
    results: dict[str, tuple[str, object]] = {}

    def submit(label: str) -> None:
        db = postgres_session_factory()
        try:
            actor = db.get(User, instructor_id)
            barrier.wait(timeout=10)
            availability = phase2_service.submit_availability(
                db,
                actor,
                WS,
                unavailable=False,
                entries=offers[label],
            )
            db.commit()
            current = sorted(
                entry.starts_at
                for entry in availability.entries
                if entry.is_current
            )
            results[label] = ("ok", current)
        except phase2_service.AvailabilityError as exc:
            db.rollback()
            results[label] = ("error", exc.code)
        except Exception as exc:  # pragma: no cover - diagnóstico
            db.rollback()
            results[label] = ("unexpected", repr(exc))
        finally:
            db.close()

    threads = [
        Thread(target=submit, args=(label,), name=f"submit-{label}")
        for label in offers
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()

    assert {label: result[0] for label, result in results.items()} == {
        "a": "ok",
        "b": "ok",
    }, results
    winner = {label: result[1] for label, result in results.items()}
    assert winner["a"] in expected_starts.values()
    assert winner["b"] in expected_starts.values()

    postgres_db.expire_all()
    availability = postgres_db.scalar(
        select(WeeklyAvailability).where(
            WeeklyAvailability.cycle_id
            == postgres_db.scalar(
                select(WeeklyCycle.id).where(WeeklyCycle.week_start == WS)
            ),
            WeeklyAvailability.instructor_id == instructor_id,
        )
    )
    assert availability is not None
    rows = postgres_db.scalars(
        select(AvailabilityEntry).where(
            AvailabilityEntry.availability_id == availability.id
        )
    ).all()
    current = [row for row in rows if row.is_current]
    # Duas gerações de duas ofertas cada; só uma geração fica vigente.
    assert len(rows) == 4
    assert len(current) == 2
    assert sorted(row.starts_at for row in current) in expected_starts.values()
