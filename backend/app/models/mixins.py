"""Mixins comuns de coluna, sem dependência da classe declarativa.

Cada modelo combina explicitamente: ``class User(Base, UUIDPk, Timestamped):``.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDPk:
    """Chave primária UUID gerada pela aplicação.

    O tipo genérico ``Uuid`` funciona tanto no PostgreSQL quanto no SQLite
    (usado nos testes unitários isolados).
    """

    @declared_attr
    def id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamped:
    """Campos de auditoria ``created_at``/``updated_at`` (timezone-aware)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )
