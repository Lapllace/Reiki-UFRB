"""Rotas da Fase 3: cancelamento de sessão e cobertura.

Permissões: apenas o ministrante responsável cancela; apenas o destinatário
do convite aceita/recusa. Proteção CSRF (`enforce_same_origin`) mantida.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import enforce_same_origin, require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.phase2 import (
    AcceptCoverResultOut,
    CancelSessionIn,
    CoverInviteOut,
    CoverInviteStatus,
)
from app.services import cover_service

router = APIRouter(tags=["coverage"])
instructor_router = APIRouter(prefix="/instructor", tags=["instructor"])


def _invite_out(invite, *, accepted: bool = False) -> CoverInviteOut:
    return CoverInviteOut(
        id=invite.id,
        status=CoverInviteStatus(invite.status),
        session_id=invite.request.session_id,
        created_at=invite.created_at,
        expires_at=None,  # sem expiração automática até decisão institucional
        accepted=accepted,
    )


@instructor_router.post("/sessions/{session_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_session(
    session_id: uuid.UUID,
    payload: CancelSessionIn,
    user: User = Depends(require_role(Role.INSTRUCTOR, Role.COORDINATOR)),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        request = cover_service.cancel_session(db, user, session_id, payload.reason)
    except cover_service.CoverError as exc:
        code_status = {"session_not_found": 404, "not_owner": 403}.get(exc.code, 409)
        raise HTTPException(
            status_code=code_status, detail=str(exc), headers={"X-Error-Code": exc.code}
        )
    return {
        "coverRequestId": str(request.id),
        "status": request.status.value,
        "sessionId": str(request.session_id),
    }


@instructor_router.get("/cover-invites", response_model=list[CoverInviteOut])
def list_cover_invites(
    user: User = Depends(require_role(Role.INSTRUCTOR, Role.COORDINATOR)),
    db: Session = Depends(get_db),
) -> list[CoverInviteOut]:
    invites = cover_service.list_invites_for(db, user.id)
    return [_invite_out(i) for i in invites]


@instructor_router.post(
    "/cover-invites/{invite_id}/accept", response_model=AcceptCoverResultOut
)
def accept_cover(
    invite_id: uuid.UUID,
    user: User = Depends(require_role(Role.INSTRUCTOR, Role.COORDINATOR)),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> AcceptCoverResultOut:
    try:
        outcome, invite = cover_service.accept_invite(db, user, invite_id)
    except cover_service.CoverError as exc:
        code_status = {"not_found": 404}.get(exc.code, 409)
        raise HTTPException(
            status_code=code_status, detail=str(exc), headers={"X-Error-Code": exc.code}
        )
    return AcceptCoverResultOut(
        outcome=outcome,
        invite=_invite_out(invite, accepted=(outcome == "accepted")),
    )


@instructor_router.post(
    "/cover-invites/{invite_id}/decline", response_model=CoverInviteOut
)
def decline_cover(
    invite_id: uuid.UUID,
    user: User = Depends(require_role(Role.INSTRUCTOR, Role.COORDINATOR)),
    _csrf: None = Depends(enforce_same_origin),
    db: Session = Depends(get_db),
) -> CoverInviteOut:
    try:
        invite, _request = cover_service.decline_invite(db, user, invite_id)
    except cover_service.CoverError as exc:
        code_status = {"not_found": 404}.get(exc.code, 409)
        raise HTTPException(
            status_code=code_status, detail=str(exc), headers={"X-Error-Code": exc.code}
        )
    return _invite_out(invite)
