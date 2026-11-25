"""Read-only public inventory adapter; independent Ticketing DB and Events authority."""
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ticketing_service.persistence import OrderItemRow, SeatRow, TicketRow, ZoneRow, engine
from ticketing_service.purchase_admission import PublicEventData, valid_service_url
from ticketing_service.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Inventory"])
NO_STORE = {"Cache-Control": "no-store"}


class SeatResponse(BaseModel):
    id: UUID
    label: str
    available: bool


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


def inventory_session():
    with Session(engine) as db:
        yield db


class PublishedEventVerifier:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self.url = valid_service_url(settings.events_service_url)
        self.transport = transport

    def require_published(self, event_id: UUID) -> None:
        try:
            with httpx.Client(
                timeout=settings.purchase_timeout_seconds, transport=self.transport,
                follow_redirects=False, trust_env=False,
            ) as client:
                response = client.get(self.url + f"/api/v1/events/{event_id}")
        except httpx.RequestError as error:
            raise HTTPException(503, "Events unavailable", headers=NO_STORE) from error
        if response.status_code == 404:
            raise HTTPException(404, "Event not found", headers=NO_STORE)
        if response.status_code != 200:
            raise HTTPException(503, "Events verification unavailable", headers=NO_STORE)
        try:
            record = PublicEventData.model_validate(response.json())
        except (ValueError, TypeError) as error:
            raise HTTPException(503, "Invalid Events response", headers=NO_STORE) from error
        if record.id != event_id or record.status != "published":
            raise HTTPException(404, "Event not found", headers=NO_STORE)


def verifier() -> PublishedEventVerifier:
    try:
        return PublishedEventVerifier()
    except ValueError as error:
        raise HTTPException(503, "Events integration unavailable", headers=NO_STORE) from error


def inventory_snapshot(db: Session, event_id: UUID) -> InventoryResponse:
    zones = db.scalars(
        select(ZoneRow).where(ZoneRow.event_id == event_id).order_by(ZoneRow.name, ZoneRow.id)
    ).all()
    zone_ids = [zone.id for zone in zones if zone.mode == "numbered"]
    seats = db.scalars(
        select(SeatRow).where(SeatRow.zone_id.in_(zone_ids)).order_by(SeatRow.label, SeatRow.id)
    ).all() if zone_ids else []
    sold = set(db.scalars(
        select(TicketRow.seat_id).join(
            OrderItemRow, TicketRow.order_item_id == OrderItemRow.id,
        ).where(TicketRow.seat_id.is_not(None), OrderItemRow.zone_id.in_(zone_ids))
    ).all()) if zone_ids else set()
    by_zone: dict[UUID, list[SeatResponse]] = {zone_id: [] for zone_id in zone_ids}
    for seat in seats:
        by_zone[seat.zone_id].append(
            SeatResponse(id=seat.id, label=seat.label, available=seat.id not in sold)
        )
    return InventoryResponse(event_id=event_id, zones=[
        ZoneResponse(
            id=zone.id, name=zone.name, mode=zone.mode, price_minor=zone.price_minor,
            currency=zone.currency, capacity=zone.capacity,
            available=zone.available if zone.mode == "general" else sum(
                int(seat.available) for seat in by_zone[zone.id]
            ),
            seats=by_zone.get(zone.id, []),
        ) for zone in zones
    ])


@router.get("/events/{event_id}/inventory", response_model=InventoryResponse)
def public_inventory(
    event_id: UUID,
    response: Response,
    events: Annotated[PublishedEventVerifier, Depends(verifier)],
    db: Annotated[Session, Depends(inventory_session)],
):
    response.headers["Cache-Control"] = "no-store"
    events.require_published(event_id)
    return inventory_snapshot(db, event_id)
