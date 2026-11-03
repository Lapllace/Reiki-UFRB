"""Modelo de usuários. Papéis refletem o contrato do frontend."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk


class Role(str, enum.Enum):
    PARTICIPANT = "participant"
    INSTRUCTOR = "instructor"
    COORDINATOR = "coordinator"


class User(Base, UUIDPk, Timestamped):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Normalizado para minúsculas e aparado no serviço de aplicação.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        # Persiste os VALORES ("participant"), não os nomes — contrato do frontend.
        Enum(
            Role,
            name="user_role",
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
            validate_strings=True,
        ),
        nullable=False,
        default=Role.PARTICIPANT,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Mantido para auditoria (usuários desativados não excluem histórico).
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} role={self.role}>"
