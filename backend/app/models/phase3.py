"""Fase 3: solicitação de cobertura e convites individuais.

Fluxo: ministrante cancela a própria sessão → sessão vai a `needs_cover` →
uma única `CoverRequest` é criada e convites individuais vão a todos os
demais ministrantes ativos. O primeiro aceite registrado pelo banco assume
a sessão. Ninguém aceitando → `uncovered`.

Não há prazos nem expiração automática (a definir pela coordenação).
Convites nunca são apagados: histórico preservado.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk


class CoverRequestStatus(str, enum.Enum):
    OPEN = "open"
    COVERED = "covered"
    UNCOVERED = "uncovered"


class CoverInviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"    # aceite vencedor (assume a sessão)
    TAKEN = "taken"          # disputa perdida; outro convite venceu
    DECLINED = "declined"
    EXPIRED = "expired"      # estado reservado; sem expiração automática
    WITHDRAWN = "withdrawn"  # retirado pela coordenação (etapa futura)


class CoverRequest(Base, UUIDPk, Timestamped):
    """Solicitação de cobertura para uma sessão (uma por cancelamento)."""

    __tablename__ = "cover_requests"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reiki_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Ministrante que cancelou (pode ter sido removido depois; sem FK dura).
    original_instructor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[CoverRequestStatus] = mapped_column(
        String(20), nullable=False, default=CoverRequestStatus.OPEN
    )
    # Estado da sessão antes de `needs_cover` (restaurado ao assumirem).
    previous_session_status: Mapped[str] = mapped_column(String(20), nullable=False)
    covered_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    invites: Mapped[list["CoverInvite"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )

    # Uma única solicitação aberta/registrada por sessão.
    __table_args__ = (
        Index(
            "uq_cover_requests_session",
            "session_id",
            unique=True,
        ),
    )


class CoverInvite(Base, UUIDPk):
    """Convite individual de cobertura (histórico preservado)."""

    __tablename__ = "cover_invites"

    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cover_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_instructor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CoverInviteStatus] = mapped_column(
        String(20), nullable=False, default=CoverInviteStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Datas de auditoria: primeiro aceite vencedor, disputa perdida, recusa.
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    declined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    request: Mapped[CoverRequest] = relationship(back_populates="invites")

    __table_args__ = (
        UniqueConstraint(
            "request_id", "invited_instructor_id", name="uq_cover_invite_req_instructor"
        ),
        Index(
            "ix_cover_invites_instructor_status",
            "invited_instructor_id",
            "status",
        ),
    )
