"""Leitura de locais ativos."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.location import Location
from app.schemas.domain import LocationOut

router = APIRouter(tags=["locations"])


@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db)) -> list[LocationOut]:
    stmt = select(Location).where(Location.is_active.is_(True)).order_by(Location.name)
    return [LocationOut.model_validate(loc) for loc in db.scalars(stmt)]
