"""Dependências do FastAPI: banco, autenticação e autorização."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.session_auth import AuthSession
from app.models.user import Role, User


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias="reiki_session"),
) -> User | None:
    """Resolve o usuário a partir do cookie opaco; None quando não há sessão válida."""
    if not session_cookie:
        return None
    settings = get_settings()
    now = datetime.now(UTC)
    auth_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_hash == _hash_token(session_cookie),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .one_or_none()
    )
    if auth_session is None:
        return None
    user = db.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        return None
    # Renovação deslizante simples da expiração no servidor.
    auth_session.expires_at = now + timedelta(minutes=settings.session_ttl_minutes)
    return user


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """Exige usuário autenticado (401 no formato que o frontend espera)."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão não autenticada.",
            headers={"WWW-Authenticate": "Session"},
        )
    return user


def require_role(*allowed: Role) -> Callable[[User], User]:
    """Fábrica de dependência: exige um dos papéis informados (403 caso contrário)."""

    def dependency(user: User = Depends(require_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta ação.",
            )
        return user

    return dependency


def enforce_same_origin(request: Request) -> None:
    """Proteção CSRF para métodos que alteram estado, complementando SameSite.

    Regra: se houver header `Origin`, ele deve ser uma das origens permitidas
    (CORS configurado). Requisições sem `Origin` (curl, testes) passam.
    """

    origin = request.headers.get("origin")
    if origin is None:
        return
    allowed = {o.rstrip("/") for o in get_settings().cors_origin_list}
    if origin.rstrip("/") not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem não permitida para operações que alteram estado.",
        )
