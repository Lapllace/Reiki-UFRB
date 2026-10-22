"""Locais onde as sessões de Reiki acontecem."""

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import Timestamped, UUIDPk


class Location(Base, UUIDPk, Timestamped):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    map_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
