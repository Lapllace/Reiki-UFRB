"""Fase 4: casos de reorganização e histórico de decisões."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk


class ReallocationStatus(str, enum.Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class ReallocationAlternative(str, enum.Enum):
    EXTRA_SESSION = "extra_session"
    FUTURE_PRIORITY = "future_priority"


class ReallocationCase(Base, UUIDPk, Timestamped):
    """Uma decisão administrativa para uma inscrição afetada."""

    __tablename__ = "reallocation_cases"

    origin_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reiki_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    origin_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[ReallocationStatus] = mapped_column(String(20), nullable=False)
    alternative: Mapped[ReallocationAlternative | None] = mapped_column(
        String(30), nullable=True
    )
    target_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reiki_sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    priority_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    dismissal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    origin_session = relationship("ReikiSession", foreign_keys=[origin_session_id], lazy="joined")
    origin_enrollment = relationship("Enrollment", foreign_keys=[origin_enrollment_id], lazy="joined")
    participant = relationship("User", foreign_keys=[participant_id], lazy="joined")
    target_session = relationship("ReikiSession", foreign_keys=[target_session_id], lazy="joined")
    history = relationship(
        "ReallocationHistory", back_populates="case", cascade="all, delete-orphan",
        order_by="ReallocationHistory.created_at",
    )

    __table_args__ = (
        UniqueConstraint("origin_enrollment_id", name="uq_reallocation_origin_enrollment"),
    )


class ReallocationHistory(Base, UUIDPk):
    """Eventos imutáveis relevantes para auditoria da reorganização."""

    __tablename__ = "reallocation_history"

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reallocation_cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    case = relationship("ReallocationCase", back_populates="history")
