"""Base declarativa única do projeto (sem importações circulares)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa única do projeto."""
