"""Fase 3: cancelamento de sessão, cobertura e primeiro aceite.

SQLite valida transições de estado, permissões e persistência de inscrições.
A corrida do primeiro aceite (FOR UPDATE) só é testável no PostgreSQL —
marcada `postgres_pending` e SKIPPED sem TEST_DATABASE_URL.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.models.phase2 import Enrollment, EnrollmentStatus
from app.models.phase3 import (
    CoverInvite,
    CoverInviteStatus,
    CoverRequest,
    CoverRequestStatus,
)
from app.models.session_week import SessionStatus
from app.models.user import Role, User
from app.services import cover_service, phase2_service
from tests.conftest import login
from tests.test_auth import PASSWORD
from tests.test_phase2 import _make_participant, _make_session


def _instructor(db, n=None) -> User:
    u = User(
        name=f"Instrutor {n or uuid.uuid4().hex[:6]}",
        email=f"i{uuid.uuid4().hex[:8]}@x.local",
        password_hash=hash_password(PASSWORD),
        role=Role.INSTRUCTOR,
    )
    db.add(u)
    return u


def _participant(db) -> User:
    u = User(
        name=f"Participante {uuid.uuid4().hex[:6]}",
        email=f"p{uuid.uuid4().hex[:8]}@x.local",
        password_hash=hash_password(PASSWORD),
        role=Role.PARTICIPANT,
    )
    db.add(u)
    db.commit()
    return u


def _refresh(db, *objs):
    for o in objs:
        db.refresh(o)


def _owned_session(db, capacity=2, status=SessionStatus.OPEN, extra_instructors=0):
    """Sessão COM ministrante responsável (o fluxo de cobertura exige um)."""
    s = _make_session(db, capacity=capacity, status=status)
    owner = _instructor(db)
    db.commit()
    s.instructor_id = owner.id
    db.commit()
    extras = [_instructor(db) for _ in range(extra_instructors)]
    db.commit()
    return s, owner, extras


# --------------------------- Domínio ---------------------------


def test_cancel_by_owner_creates_single_request(db) -> None:
    s, owner, _extras = _owned_session(db, extra_instructors=1)
    req = cover_service.cancel_session(db, owner, s.id, reason="imprevisto")
    _refresh(db, s, req)
    assert s.status == SessionStatus.NEEDS_COVER
    assert req.status == CoverRequestStatus.OPEN
    assert req.previous_session_status == SessionStatus.OPEN.value
    assert db.query(CoverRequest).count() == 1
    # Idempotência: repetir não cria nova solicitação.
    req2 = cover_service.cancel_session(db, owner, s.id)
    assert req2.id == req.id
    assert db.query(CoverRequest).count() == 1


def test_cancel_by_non_owner_rejected(db) -> None:
    s = _make_session(db)
    other = _instructor(db)
    db.commit()
    with pytest.raises(cover_service.CoverError) as exc:
        cover_service.cancel_session(db, other, s.id)
    assert exc.value.code == "not_owner"


def test_cancel_invalid_state_rejected(db) -> None:
    s, owner, _extras = _owned_session(db)
    s.status = SessionStatus.CANCELLED
    db.commit()
    with pytest.raises(cover_service.CoverError) as exc:
        cover_service.cancel_session(db, owner, s.id)
    assert exc.value.code == "not_cancellable"


def test_invites_all_others_excluding_owner_no_duplicates(db) -> None:
    s, owner, _extras = _owned_session(db, extra_instructors=3)
    req = cover_service.cancel_session(db, owner, s.id)
    invites = req.invites
    invited_ids = [i.invited_instructor_id for i in invites]
    assert len(invites) == 3
    assert owner.id not in invited_ids
    assert len(set(invited_ids)) == 3


def test_no_other_instructors_resolves_uncovered(db) -> None:
    s, owner, _extras = _owned_session(db)
    req = cover_service.cancel_session(db, owner, s.id)
    _refresh(db, req, s)
    assert req.status == CoverRequestStatus.UNCOVERED
    assert req.resolved_at is not None
    assert s.status == SessionStatus.UNCOVERED


def test_accept_first_wins_restores_previous_status(db) -> None:
    s, owner, [i2] = _owned_session(db, extra_instructors=1)
    req = cover_service.cancel_session(db, owner, s.id)
    invite = req.invites[0]
    outcome, _inv = cover_service.accept_invite(db, i2, invite.id)
    _refresh(db, s, req)
    assert outcome == "accepted"
    assert s.instructor_id == i2.id
    assert s.status == SessionStatus.OPEN  # estado anterior restaurado
    assert req.status == CoverRequestStatus.COVERED
    assert req.covered_by == i2.id
    assert req.resolved_at is not None


def test_accept_full_previous_status_restored(db) -> None:
    s, owner, [i2] = _owned_session(db, capacity=1, status=SessionStatus.FULL, extra_instructors=1)
    req = cover_service.cancel_session(db, owner, s.id)
    outcome, _ = cover_service.accept_invite(db, i2, req.invites[0].id)
    _refresh(db, s)
    assert outcome == "accepted"
    assert s.status == SessionStatus.FULL


def test_second_invite_already_taken(db) -> None:
    s, owner, [i2, i3] = _owned_session(db, extra_instructors=2)
    req = cover_service.cancel_session(db, owner, s.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    inv3 = next(i for i in req.invites if i.invited_instructor_id == i3.id)
    outcome, _ = cover_service.accept_invite(db, i2, inv2.id)
    assert outcome == "accepted"
    outcome3, inv3 = cover_service.accept_invite(db, i3, inv3.id)
    assert outcome3 == "already_taken"
    _refresh(db, inv3, s)
    assert inv3.status == CoverInviteStatus.TAKEN
    assert inv3.accepted_at is None
    assert s.instructor_id == i2.id


def test_accept_by_non_recipient_rejected(db) -> None:
    s, owner, [i2, i3] = _owned_session(db, extra_instructors=2)
    req = cover_service.cancel_session(db, owner, s.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    with pytest.raises(cover_service.CoverError) as exc:
        cover_service.accept_invite(db, i3, inv2.id)
    assert exc.value.code == "not_found"


def test_decline_then_uncovered_when_all_decline(db) -> None:
    s, owner, [i2, i3] = _owned_session(db, extra_instructors=2)
    req = cover_service.cancel_session(db, owner, s.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    inv3 = next(i for i in req.invites if i.invited_instructor_id == i3.id)
    cover_service.decline_invite(db, i2, inv2.id)
    _inv, request = cover_service.decline_invite(db, i3, inv3.id)
    _refresh(db, request, s)
    assert request.status == CoverRequestStatus.UNCOVERED
    assert s.status == SessionStatus.UNCOVERED
    # Histórico preservado: convites permanecem no banco.
    assert db.query(CoverInvite).count() == 2


def test_decline_not_pending_rejected(db) -> None:
    s, owner, [i2, i3] = _owned_session(db, extra_instructors=2)
    req = cover_service.cancel_session(db, owner, s.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    inv3 = next(i for i in req.invites if i.invited_instructor_id == i3.id)
    cover_service.accept_invite(db, i2, inv2.id)
    with pytest.raises(cover_service.CoverError) as exc:
        cover_service.decline_invite(db, i3, inv3.id)
    assert exc.value.code == "not_pending"


def test_enrollments_preserved_through_cover(db) -> None:
    s, owner, [i2] = _owned_session(db, capacity=2, extra_instructors=1)
    p1 = _make_participant(db)
    p2 = _make_participant(db)
    e1 = phase2_service.create_enrollment(db, p1, s.id)
    e2 = phase2_service.create_enrollment(db, p2, s.id)
    db.commit()
    req = cover_service.cancel_session(db, owner, s.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    cover_service.accept_invite(db, i2, inv2.id)
    _refresh(db, e1, e2)
    assert e1.status == EnrollmentStatus.CONFIRMED
    assert e2.status == EnrollmentStatus.CONFIRMED
    assert e1.session_id == s.id and e2.session_id == s.id
    assert db.query(Enrollment).filter(Enrollment.session_id == s.id).count() == 2


def test_enrollments_preserved_when_uncovered(db) -> None:
    s, owner, _extras = _owned_session(db, capacity=2)
    p1 = _make_participant(db)
    e1 = phase2_service.create_enrollment(db, p1, s.id)
    db.commit()
    req = cover_service.cancel_session(db, owner, s.id)
    _refresh(db, req, s, e1)
    assert req.status == CoverRequestStatus.UNCOVERED
    assert s.status == SessionStatus.UNCOVERED
    # Inscrição não apagada nem cancelada silenciosamente.
    assert e1.status == EnrollmentStatus.CONFIRMED


# ------------------------------ API ------------------------------


def test_api_cancel_and_accept_flow(client: TestClient, db) -> None:
    s, owner, [i2] = _owned_session(db, extra_instructors=1)
    login(client, owner.email, PASSWORD)
    resp = client.post(f"/instructor/sessions/{s.id}/cancel", json={"reason": "viagem"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "open"
    assert body["sessionId"] == str(s.id)

    login(client, i2.email, PASSWORD)
    invites = client.get("/instructor/cover-invites").json()
    assert len(invites) == 1
    assert invites[0]["sessionId"] == str(s.id)
    assert invites[0]["status"] == "pending"
    invite_id = invites[0]["id"]
    resp = client.post(f"/instructor/cover-invites/{invite_id}/accept")
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "accepted"
    assert body["invite"]["accepted"] is True


def test_api_already_taken_contract(client: TestClient, db) -> None:
    s, owner, [i2, i3] = _owned_session(db, extra_instructors=2)
    req = cover_service.cancel_session(db, owner, s.id)
    inv3 = next(i for i in req.invites if i.invited_instructor_id == i3.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    cover_service.accept_invite(db, i2, inv2.id)
    db.commit()
    login(client, i3.email, PASSWORD)
    resp = client.post(f"/instructor/cover-invites/{inv3.id}/accept")
    assert resp.status_code == 200
    body = resp.json()
    # Contrato AcceptCoverResult: outcome + estado atual do convite.
    assert body["outcome"] == "already_taken"
    assert body["invite"]["status"] == "taken"


def test_api_decline_endpoint(client: TestClient, db) -> None:
    s, owner, [i2] = _owned_session(db, extra_instructors=1)
    req = cover_service.cancel_session(db, owner, s.id)
    inv2 = next(i for i in req.invites if i.invited_instructor_id == i2.id)
    db.commit()
    login(client, i2.email, PASSWORD)
    resp = client.post(f"/instructor/cover-invites/{inv2.id}/decline")
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"


def test_api_unauthenticated_rejected(client: TestClient, db) -> None:
    s, _owner, _extras = _owned_session(db)
    resp = client.post(f"/instructor/sessions/{s.id}/cancel", json={"reason": None})
    assert resp.status_code == 401


def test_api_participant_forbidden(client: TestClient, db) -> None:
    s, _owner, _extras = _owned_session(db)
    p = _participant(db)
    login(client, p.email, PASSWORD)
    resp = client.get("/instructor/cover-invites")
    assert resp.status_code == 403
    resp = client.post(f"/instructor/sessions/{s.id}/cancel", json={})
    assert resp.status_code == 403


@pytest.mark.postgres_pending
def test_accept_race_only_one_wins(postgres_db, postgres_session_factory) -> None:
    session_row, owner, _extras = _owned_session(postgres_db, extra_instructors=2)
    participant = _make_participant(postgres_db)
    phase2_service.create_enrollment(postgres_db, participant, session_row.id)
    request = cover_service.cancel_session(postgres_db, owner, session_row.id, "imprevisto")
    postgres_db.commit()
    invites = postgres_db.query(CoverInvite).filter(
        CoverInvite.request_id == request.id
    ).all()
    invite_ids = [invite.id for invite in invites[:2]]
    invited_users = {invite.id: invite.invited_instructor_id for invite in invites}
    barrier = Barrier(2)

    def attempt(invite_id):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            instructor = db.get(User, invited_users[invite_id])
            outcome, _invite = cover_service.accept_invite(db, instructor, invite_id)
            db.commit()
            return outcome
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, invite_ids))
    assert sorted(outcomes) == ["accepted", "already_taken"]
    # Expira o identity map para forçar nova leitura do banco após as transações
    # concorrentes confirmarem. Sem expire_all(), o SQLAlchemy pode retornar o
    # objeto em cache com o estado anterior ao commit das threads.
    postgres_db.expire_all()
    refreshed = postgres_db.scalars(
        select(CoverRequest).where(CoverRequest.id == request.id)
    ).one()
    assert refreshed.status == CoverRequestStatus.COVERED
    assert postgres_db.query(CoverInvite).filter(
        CoverInvite.status == CoverInviteStatus.ACCEPTED
    ).count() == 1
    assert postgres_db.query(Enrollment).filter(
        Enrollment.session_id == session_row.id
    ).count() == 1


@pytest.mark.postgres_pending
def test_cancel_race_single_request(postgres_db, postgres_session_factory) -> None:
    session_row, owner, _extras = _owned_session(postgres_db, extra_instructors=1)
    owner_id = owner.id
    session_id = session_row.id
    barrier = Barrier(2)

    def attempt(_):
        db = postgres_session_factory()
        try:
            barrier.wait(timeout=10)
            instructor = db.get(User, owner_id)
            request = cover_service.cancel_session(db, instructor, session_id, "imprevisto")
            db.commit()
            return request.id
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert all(not isinstance(result, Exception) for result in results)
    assert len(set(results)) == 1
    assert postgres_db.query(CoverRequest).filter(
        CoverRequest.session_id == session_id
    ).count() == 1
    assert postgres_db.query(Enrollment).filter(
        Enrollment.session_id == session_id
    ).count() == 1
