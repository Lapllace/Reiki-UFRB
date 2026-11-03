"""Gestão do ciclo semanal (Sprint 1 da Etapa B) — PostgreSQL real.

Cobre a correção do GET /coordination/cycles/{weekStart} (estado real das
disponibilidades) e o POST /coordination/cycles (criação idempotente).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import create_app
from app.models.cycle import CyclePhase, WeeklyCycle
from app.models.phase2 import WeeklyAvailability
from app.models.user import Role, User
from app.services import phase2_service
from tests.conftest import login
from tests.test_auth import PASSWORD

# 2026-11-09 é segunda-feira; 2026-11-08 é domingo; 2026-11-11 é quarta.
WS = date(2026, 11, 9)

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


def _make_cycle(db: Session, week_start: date = WS) -> WeeklyCycle:
    cycle = WeeklyCycle(
        week_start=week_start,
        phase=CyclePhase.COLLECTING_AVAILABILITY,
    )
    db.add(cycle)
    db.commit()
    return cycle


def _entries(count: int, day: date = WS) -> list[dict]:
    base = datetime(day.year, day.month, day.day, 14, 0, tzinfo=UTC)
    return [
        {
            "kind": "available",
            "starts_at": base + timedelta(days=i),
            "ends_at": base + timedelta(days=i, hours=1),
            "location_id": None,
            "note": None,
        }
        for i in range(count)
    ]


def _submit(
    db: Session,
    instructor: User,
    *,
    week_start: date = WS,
    unavailable: bool = False,
    entries: int = 2,
) -> WeeklyAvailability:
    submission = phase2_service.submit_availability(
        db,
        instructor,
        week_start,
        unavailable=unavailable,
        entries=[] if unavailable else _entries(entries, week_start),
    )
    db.commit()
    return submission


def _rows_by_instructor(body: dict) -> dict[str, dict]:
    return {row["instructorId"]: row for row in body["instructors"]}


def test_get_cycle_without_submissions_lists_all_active_instructors_as_pending(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    first = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante A")
    second = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante B")
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.get(f"/coordination/cycles/{WS.isoformat()}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weekStart"] == WS.isoformat()
    rows = _rows_by_instructor(body)
    assert set(rows) == {str(first.id), str(second.id)}
    for row in rows.values():
        assert row["status"] == "pending"
        assert row["submittedAt"] is None
        assert row["sessionsOffered"] == 0
        # Contrato existente do frontend preservado.
        assert row["instructor"]["name"] == row["name"]


def test_get_cycle_reflects_submitted_availability(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante Disponível")
    submission = _submit(postgres_db, instructor, entries=3)
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.get(f"/coordination/cycles/{WS.isoformat()}")

    assert response.status_code == 200, response.text
    row = _rows_by_instructor(response.json())[str(instructor.id)]
    assert row["status"] == "submitted"
    assert row["sessionsOffered"] == 3
    assert row["submittedAt"] is not None
    returned_at = datetime.fromisoformat(row["submittedAt"].replace("Z", "+00:00"))
    assert returned_at == submission.submitted_at.astimezone(UTC)


def test_get_cycle_reflects_declared_unavailability(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante Indisponível")
    submission = _submit(postgres_db, instructor, unavailable=True)
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.get(f"/coordination/cycles/{WS.isoformat()}")

    assert response.status_code == 200, response.text
    row = _rows_by_instructor(response.json())[str(instructor.id)]
    assert row["status"] == "unavailable"
    assert row["sessionsOffered"] == 0
    assert row["submittedAt"] is not None
    assert datetime.fromisoformat(
        row["submittedAt"].replace("Z", "+00:00")
    ) == submission.submitted_at.astimezone(UTC)


def test_get_cycle_excludes_inactive_instructors(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    active = _make_user(postgres_db, Role.INSTRUCTOR, "Ativo")
    inactive = _make_user(postgres_db, Role.INSTRUCTOR, "Inativo", active=False)
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.get(f"/coordination/cycles/{WS.isoformat()}")

    assert response.status_code == 200, response.text
    rows = _rows_by_instructor(response.json())
    assert str(active.id) in rows
    assert str(inactive.id) not in rows


def test_get_cycle_normalizes_sunday_to_monday(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    _submit(postgres_db, instructor, entries=1)
    login(postgres_client, coordinator.email, PASSWORD)

    # Domingo encerra a semana iniciada na segunda anterior.
    sunday = WS + timedelta(days=6)
    response = postgres_client.get(f"/coordination/cycles/{sunday.isoformat()}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weekStart"] == WS.isoformat()
    row = _rows_by_instructor(body)[str(instructor.id)]
    assert row["status"] == "submitted"
    assert row["sessionsOffered"] == 1


def test_post_creates_cycle_with_normalized_week_start(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    instructor = _make_user(postgres_db, Role.INSTRUCTOR, "Ministrante")
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.post(
        "/coordination/cycles", json={"weekStart": WS.isoformat()}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["weekStart"] == WS.isoformat()
    assert body["status"] == "collecting_availability"
    assert set(_rows_by_instructor(body)) == {str(instructor.id)}
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    assert cycle is not None
    assert cycle.phase == CyclePhase.COLLECTING_AVAILABILITY


def test_post_same_week_is_idempotent(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    first = postgres_client.post(
        "/coordination/cycles", json={"weekStart": WS.isoformat()}
    )
    second = postgres_client.post(
        "/coordination/cycles", json={"weekStart": WS.isoformat()}
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    count = postgres_db.scalar(
        select(func.count())
        .select_from(WeeklyCycle)
        .where(WeeklyCycle.week_start == WS)
    )
    assert count == 1


def test_post_normalizes_midweek_date_to_monday(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)
    wednesday = WS + timedelta(days=2)

    response = postgres_client.post(
        "/coordination/cycles", json={"weekStart": wednesday.isoformat()}
    )

    assert response.status_code == 201, response.text
    assert response.json()["weekStart"] == WS.isoformat()
    cycle = postgres_db.scalar(
        select(WeeklyCycle).where(WeeklyCycle.week_start == WS)
    )
    assert cycle is not None


def test_post_invalid_week_start_returns_422(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.post(
        "/coordination/cycles", json={"weekStart": "abc"}
    )

    assert response.status_code == 422


def test_post_response_includes_real_instructor_data(
    postgres_client: TestClient, postgres_db: Session
) -> None:
    _make_cycle(postgres_db)
    coordinator = _make_user(postgres_db, Role.COORDINATOR, "Coordenação")
    submitted = _make_user(postgres_db, Role.INSTRUCTOR, "Já Submeteu")
    pending = _make_user(postgres_db, Role.INSTRUCTOR, "Ainda Pendente")
    _submit(postgres_db, submitted, entries=2)
    login(postgres_client, coordinator.email, PASSWORD)

    response = postgres_client.post(
        "/coordination/cycles", json={"weekStart": WS.isoformat()}
    )

    assert response.status_code == 200, response.text
    rows = _rows_by_instructor(response.json())
    assert rows[str(submitted.id)]["status"] == "submitted"
    assert rows[str(submitted.id)]["sessionsOffered"] == 2
    assert rows[str(submitted.id)]["submittedAt"] is not None
    assert rows[str(pending.id)]["status"] == "pending"
    assert rows[str(pending.id)]["sessionsOffered"] == 0


def test_concurrent_cycle_creation_keeps_single_row(
    postgres_db: Session, postgres_session_factory
) -> None:
    barrier = Barrier(2)

    def attempt(_):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            cycle, created = phase2_service.create_or_get_cycle(db, WS)
            db.commit()
            return cycle.id, created
        except Exception as exc:  # pragma: no cover - diagnóstico
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))

    assert all(not isinstance(result, Exception) for result in results), results
    ids = {result[0] for result in results}
    assert len(ids) == 1
    assert sorted(result[1] for result in results) == [False, True]
    count = postgres_db.scalar(
        select(func.count())
        .select_from(WeeklyCycle)
        .where(WeeklyCycle.week_start == WS)
    )
    assert count == 1
