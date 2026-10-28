"""Fase 3: cancelamento de sessão pelo ministrante e cobertura.

Garantias:
- uma única solicitação de cobertura por sessão (idempotência);
- convites a TODOS os demais ministrantes ativos, sem duplicidade;
- o primeiro aceite vence: bloqueio pessimista (`FOR UPDATE`) da solicitação
  e da sessão dentro de uma única transação;
- inscrições preservadas durante a cobertura e após a substituição;
- ninguém aceitando (ou sem outros ministrantes) → `uncovered`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.phase3 import (
    CoverInvite,
    CoverInviteStatus,
    CoverRequest,
    CoverRequestStatus,
)
from app.models.session_week import ReikiSession, SessionStatus
from app.models.user import Role, User


class CoverError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _lock_session(db: Session, session_id: uuid.UUID) -> ReikiSession | None:
    # Lock pessimista da sessão para cancelamento/cobertura.
    # of=ReikiSession evita bloquear relacionamentos joined nullable (instructor, cycle).
    stmt = (
        select(ReikiSession).where(ReikiSession.id == session_id).with_for_update(of=ReikiSession)
    )
    return db.execute(stmt).scalar_one_or_none()


def _lock_request(db: Session, request_id: uuid.UUID) -> CoverRequest | None:
    # Lock pessimista da solicitação de cobertura.
    # of=CoverRequest por consistência (embora não tenha relacionamentos joined nullable).
    stmt = select(CoverRequest).where(CoverRequest.id == request_id).with_for_update(of=CoverRequest)
    return db.execute(stmt).scalar_one_or_none()


def active_instructors_excluding(db: Session, instructor_id: uuid.UUID | None) -> list[User]:
    stmt = (
        select(User)
        .where(User.role == Role.INSTRUCTOR, User.is_active.is_(True))
        .order_by(User.created_at)
    )
    if instructor_id is not None:
        stmt = stmt.where(User.id != instructor_id)
    return list(db.scalars(stmt))


def cancel_session(
    db: Session, instructor: User, session_id: uuid.UUID, reason: str | None = None
) -> CoverRequest:
    """Cancelamento pelo responsável: transacional e idempotente.

    - Só o ministrante responsável pode cancelar (validado aqui e na rota).
    - Estados que permitem: scheduled, open, full.
    - Repeated calls return the existing open/covered request (idempotente).
    """
    session_row = _lock_session(db, session_id)
    if session_row is None:
        raise CoverError("session_not_found", "Sessão não encontrada.")
    if session_row.instructor_id != instructor.id:
        raise CoverError(
            "not_owner", "Apenas o ministrante responsável pode cancelar a sessão."
        )

    # A solicitação persistida representa o primeiro cancelamento e torna
    # chamadas repetidas idempotentes, mesmo após a sessão mudar de estado.
    existing = db.scalar(
        select(CoverRequest).where(CoverRequest.session_id == session_id)
    )
    if existing is not None:
        return existing

    if session_row.status not in (
        SessionStatus.SCHEDULED,
        SessionStatus.OPEN,
        SessionStatus.FULL,
    ):
        raise CoverError(
            "not_cancellable",
            "Estado atual da sessão não permite cancelamento com cobertura.",
        )

    previous_status = session_row.status
    session_row.status = SessionStatus.NEEDS_COVER
    session_row.cancelled_at = datetime.now(UTC)
    session_row.cancel_reason = reason

    request = CoverRequest(
        session_id=session_id,
        original_instructor_id=instructor.id,
        reason=reason,
        status=CoverRequestStatus.OPEN,
        previous_session_status=previous_status.value,
    )
    db.add(request)
    db.flush()

    candidates = active_instructors_excluding(db, instructor.id)
    if not candidates:
        # Ninguém para convidar: resolve imediatamente como uncovered.
        request.status = CoverRequestStatus.UNCOVERED
        request.resolved_at = datetime.now(UTC)
        session_row.status = SessionStatus.UNCOVERED
        from app.services.phase4_service import create_cases_for_uncovered_session
        create_cases_for_uncovered_session(db, session_id)
        db.flush()
        return request

    now = datetime.now(UTC)
    for candidate in candidates:
        db.add(
            CoverInvite(
                request_id=request.id,
                invited_instructor_id=candidate.id,
                status=CoverInviteStatus.PENDING,
                created_at=now,
            )
        )
    db.flush()
    return request


def list_invites_for(db: Session, instructor_id: uuid.UUID) -> list[CoverInvite]:
    return list(
        db.scalars(
            select(CoverInvite)
            .where(CoverInvite.invited_instructor_id == instructor_id)
            .order_by(CoverInvite.created_at)
        )
    )


def accept_invite(
    db: Session, instructor: User, invite_id: uuid.UUID
) -> tuple[str, CoverInvite]:
    """Primeiro aceite vence — dentro de UMA transação.

    Retorna (outcome, invite): outcome ∈ {accepted, already_taken, expired}.
    """
    invite = db.scalar(select(CoverInvite).where(CoverInvite.id == invite_id))
    if invite is None or invite.invited_instructor_id != instructor.id:
        raise CoverError("not_found", "Convite não encontrado.")

    # Todos os caminhos de decisão bloqueiam primeiro a solicitação e depois
    # o convite, evitando que a atualização dos demais convites forme ciclo.
    request = _lock_request(db, invite.request_id)
    if request is None:
        raise CoverError("request_closed", "Solicitação não está mais aberta.")

    stmt = select(CoverInvite).where(CoverInvite.id == invite_id).with_for_update(of=CoverInvite)
    invite = db.execute(stmt).scalar_one_or_none()
    if invite is None or invite.invited_instructor_id != instructor.id:
        raise CoverError("not_found", "Convite não encontrado.")
    if invite.status == CoverInviteStatus.TAKEN:
        return "already_taken", invite
    if invite.status == CoverInviteStatus.EXPIRED:
        return "expired", invite
    if invite.status != CoverInviteStatus.PENDING:
        raise CoverError("not_pending", "Convite não está mais aberto.")
    if request.status != CoverRequestStatus.OPEN:
        invite.status = CoverInviteStatus.TAKEN
        invite.resolved_at = datetime.now(UTC)
        return "already_taken", invite

    session_row = _lock_session(db, request.session_id)
    if session_row is None:
        raise CoverError("session_not_found", "Sessão não encontrada.")

    now = datetime.now(UTC)
    # Vencedor: assume a sessão.
    invite.status = CoverInviteStatus.ACCEPTED
    invite.accepted_at = now
    request.status = CoverRequestStatus.COVERED
    request.covered_by = instructor.id
    request.resolved_at = now
    # Restaura o estado anterior, preservando inscrições e capacidade.
    try:
        session_row.status = SessionStatus(request.previous_session_status)
    except ValueError:
        session_row.status = SessionStatus.OPEN
    session_row.instructor_id = instructor.id
    # Outros convites pendentes fecham como taken (disputa perdida).
    others = db.scalars(
        select(CoverInvite).where(
            CoverInvite.request_id == request.id,
            CoverInvite.id != invite.id,
            CoverInvite.status == CoverInviteStatus.PENDING,
        )
    ).all()
    for other in others:
        other.status = CoverInviteStatus.TAKEN
        other.resolved_at = now
    db.flush()
    return "accepted", invite


def decline_invite(
    db: Session, instructor: User, invite_id: uuid.UUID
) -> tuple[CoverInvite, CoverRequest]:
    """Recusa; quando todos recusarem, resolve como uncovered.

    Operação transacional: bloqueia a solicitação para evitar corrida com
    um aceite simultâneo.
    """
    invite = db.scalar(select(CoverInvite).where(CoverInvite.id == invite_id))
    if invite is None or invite.invited_instructor_id != instructor.id:
        raise CoverError("not_found", "Convite não encontrado.")

    # A solicitação é sempre bloqueada antes do convite, como em
    # accept_invite(), para evitar deadlocks entre decisões concorrentes.
    request = _lock_request(db, invite.request_id)
    if request is None:
        raise CoverError("request_closed", "Solicitação não está mais aberta.")

    stmt = select(CoverInvite).where(CoverInvite.id == invite_id).with_for_update(of=CoverInvite)
    invite = db.execute(stmt).scalar_one_or_none()
    if invite is None or invite.invited_instructor_id != instructor.id:
        raise CoverError("not_found", "Convite não encontrado.")
    if invite.status != CoverInviteStatus.PENDING:
        raise CoverError("not_pending", "Convite não está mais aberto.")
    if request.status != CoverRequestStatus.OPEN:
        raise CoverError("request_closed", "Solicitação não está mais aberta.")

    invite.status = CoverInviteStatus.DECLINED
    invite.declined_at = datetime.now(UTC)
    invite.resolved_at = invite.declined_at

    remaining = db.scalar(
        select(CoverInvite.id)
        .where(
            CoverInvite.request_id == request.id,
            CoverInvite.status == CoverInviteStatus.PENDING,
        )
        .limit(1)
    )
    if remaining is None:
        # Todos recusaram (ou não havia convites): uncovered.
        request.status = CoverRequestStatus.UNCOVERED
        request.resolved_at = datetime.now(UTC)
        session_row = _lock_session(db, request.session_id)
        if session_row is not None:
            session_row.status = SessionStatus.UNCOVERED
            from app.services.phase4_service import create_cases_for_uncovered_session
            create_cases_for_uncovered_session(db, request.session_id)
    db.flush()
    return invite, request
