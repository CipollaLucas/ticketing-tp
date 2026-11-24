"""Inventory HTTP adapter: validates requests and translates application results."""
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from sqlalchemy.exc import IntegrityError

from app.auth import Db, StrictRequest
from app.events import Owner
from app.ticketing_core.adapters.outbound.sqlalchemy_inventory import (
    SqlAlchemyInventoryAdapter,
)
from app.ticketing_core.application.inventory import (
    ZoneCommand,
    configure_zone,
    view_inventory,
)
from app.ticketing_core.application.ports import PurchaseError

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



@router.post("/events/{event_id}/zones", response_model=ZoneResponse, status_code=201)
def create_zone(event_id: UUID, payload: ZoneCreate, user: Owner, db: Db) -> ZoneResponse:
    port = SqlAlchemyInventoryAdapter(db)
    command = ZoneCommand(
        name=payload.name, mode=payload.mode,
        price_minor=payload.price_minor, currency=payload.currency,
        capacity=payload.capacity, seats=tuple(seat.label for seat in payload.seats),
    )
    try:
        zone = configure_zone(event_id, user.id, command, port)
    except PurchaseError as error:
        raise HTTPException(error.status, error.detail) from error
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Inventory conflicts with existing data") from None
    return ZoneResponse.model_validate(zone, from_attributes=True)


@router.get("/events/{event_id}/inventory", response_model=InventoryResponse)
def public_inventory(event_id: UUID, db: Db) -> InventoryResponse:
    try:
        result = view_inventory(event_id, None, SqlAlchemyInventoryAdapter(db))
    except PurchaseError as error:
        raise HTTPException(error.status, error.detail) from error
    return InventoryResponse.model_validate(result, from_attributes=True)


@router.get("/owner/events/{event_id}/inventory", response_model=InventoryResponse)
def owner_inventory(event_id: UUID, user: Owner, db: Db) -> InventoryResponse:
    try:
        result = view_inventory(event_id, user.id, SqlAlchemyInventoryAdapter(db))
    except PurchaseError as error:
        raise HTTPException(error.status, error.detail) from error
    return InventoryResponse.model_validate(result, from_attributes=True)
