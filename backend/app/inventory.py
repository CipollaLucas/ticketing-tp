"""Inventory configuration. Availability is advisory until a purchase commits."""
from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import Db, StrictRequest, require_owner_or_admin
from app.events import Owner, utc, writable_event
from app.models import Event, Seat, Zone

router = APIRouter(prefix="/api/v1", tags=["Inventory"])
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class SeatCreate(StrictRequest):
    label: Label

    @field_validator("label")
    @classmethod
    def storable(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
        return value


class ZoneCreate(StrictRequest):
    name: Text
    mode: Literal["general", "numbered"]
    price_minor: int = Field(strict=True, ge=0, le=2147483647)
    currency: Literal["ARS", "USD", "EUR"]
    capacity: int | None = Field(default=None, strict=True, ge=1, le=1000000)
    seats: list[SeatCreate] = Field(default_factory=list, max_length=1000)

    @field_validator("name")
    @classmethod
    def storable(cls, value: str) -> str:
        return SeatCreate.storable(value)

    @model_validator(mode="after")
    def consistent_mode(self) -> Self:
        if self.mode == "general":
            if self.capacity is None or self.seats:
                raise ValueError("General requires capacity and no seats")
        elif self.capacity is not None or not self.seats:
            raise ValueError("Numbered requires seats and no capacity")
        if len({seat.label for seat in self.seats}) != len(self.seats):
            raise ValueError("Seat labels must be unique")
        return self


class SeatResponse(BaseModel):
    id: UUID
    label: str
    available: bool = True


class ZoneResponse(BaseModel):
    id: UUID
    name: str
    mode: str
    price_minor: int
    currency: str
    capacity: int | None
    available: int
    seats: list[SeatResponse]


class InventoryResponse(BaseModel):
    event_id: UUID
    zones: list[ZoneResponse]


def zone_response(zone: Zone, db: Db) -> ZoneResponse:
    seats = db.scalars(select(Seat).where(Seat.zone_id == zone.id).order_by(Seat.label)).all()
    return ZoneResponse(
        id=zone.id, name=zone.name, mode=zone.mode, price_minor=zone.price_minor,
        currency=zone.currency, capacity=zone.capacity,
        available=zone.available if zone.available is not None else len(seats),
        seats=[SeatResponse(id=s.id, label=s.label) for s in seats],
    )


@router.post("/events/{event_id}/zones", response_model=ZoneResponse, status_code=201)
def create_zone(event_id: UUID, payload: ZoneCreate, user: Owner, db: Db) -> ZoneResponse:
    event = writable_event(event_id, user, db)
    if event.status != "draft" or utc(event.start_at) <= datetime.now(UTC):
        raise HTTPException(409, "Inventory requires a future draft")
    zone = Zone(event_id=event.id, **payload.model_dump(exclude={"seats"}),
                available=payload.capacity)
    try:
        db.add(zone)
        db.flush()
        db.add_all([Seat(zone_id=zone.id, label=seat.label) for seat in payload.seats])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Inventory conflicts with existing data") from None
    return zone_response(zone, db)


def inventory(event_id: UUID, db: Db) -> InventoryResponse:
    zones = db.scalars(select(Zone).where(Zone.event_id == event_id).order_by(Zone.name)).all()
    return InventoryResponse(event_id=event_id, zones=[zone_response(z, db) for z in zones])


@router.get("/events/{event_id}/inventory", response_model=InventoryResponse)
def public_inventory(event_id: UUID, db: Db) -> InventoryResponse:
    event = db.get(Event, event_id)
    if event is None or event.status != "published":
        raise HTTPException(404, "Event not found")
    return inventory(event_id, db)


@router.get("/owner/events/{event_id}/inventory", response_model=InventoryResponse)
def owner_inventory(event_id: UUID, user: Owner, db: Db) -> InventoryResponse:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    require_owner_or_admin(user, event.owner_id)
    return inventory(event_id, db)
