"""Sessões de autenticação mantidas pelo servidor.

O cookie carrega apenas um token aleatório opaco; no banco persistimos
somente o SHA-256 dele, nunca o token em claro.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPk


class AuthSession(Base, UUIDPk):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Revogação explícita (logout ou invalidação administrativa).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_valid(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at


# Consulta por hash é o caminho crítico em toda requisição autenticada.
Index("ix_auth_sessions_token_hash", AuthSession.token_hash, unique=True)
