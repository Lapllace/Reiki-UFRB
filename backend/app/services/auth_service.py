"""Regras de autenticação: login, logout e resolução de sessão."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_session_token, new_session_token, verify_password
from app.models.session_auth import AuthSession
from app.models.user import User


class InvalidCredentials(Exception):
    """Mensagem genérica: não revela se o e-mail ou a senha está errado."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User:
    user = (
        db.query(User)
        .filter(User.email == normalize_email(email), User.is_active.is_(True))
        .one_or_none()
    )
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials("Credenciais inválidas.")
    return user


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    """Gera nova sessão (rotação: qualquer cookie anterior é irrelevante —
    apenas a nova sessão vale a partir de agora)."""
    settings = get_settings()
    token = new_session_token()
    now = datetime.now(UTC)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
    )
    db.add(auth_session)
    db.flush()
    return token, auth_session


def revoke_session(db: Session, token: str) -> bool:
    auth_session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == _hash_token(token), AuthSession.revoked_at.is_(None))
        .one_or_none()
    )
    if auth_session is None:
        return False
    auth_session.revoked_at = datetime.now(UTC)
    return True


def resolve_session(db: Session, token: str) -> User | None:
    now = datetime.now(UTC)
    auth_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_hash == _hash_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .one_or_none()
    )
    if auth_session is None:
        return None
    user = db.get(User, uuid.UUID(str(auth_session.user_id)))
    if user is None or not user.is_active:
        return None
    return user
