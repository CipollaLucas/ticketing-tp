"""Opt-in zone configuration on Ticketing's local database, authorized by Events."""
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ticketing_service.inventory import SeatSpec, ZoneSpec, validate_seat, validate_zone
from ticketing_service.inventory_http import (
    NO_STORE,
    SeatResponse,
    ZoneResponse,
    inventory_session,
)
from ticketing_service.persistence import SaleGateRow, SeatRow, ZoneRow
from ticketing_service.purchase_admission import valid_service_url
from ticketing_service.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Zone configuration"])
bearer = HTTPBearer(auto_error=False)
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class SeatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Label

    @field_validator("label")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("NUL is not allowed")
        return value


class ZoneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Text
    mode: Literal["general", "numbered"]
    price_minor: int = Field(strict=True, ge=0, le=2147483647)
    currency: Literal["ARS", "USD", "EUR"]
    capacity: int | None = Field(default=None, strict=True, ge=1, le=1000000)
    seats: list[SeatInput] = Field(default_factory=list, max_length=1000)

    @field_validator("name")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        return SeatInput.reject_nul(value)

    @model_validator(mode="after")
    def check_mode(self) -> Self:
        if self.mode == "general":
            if self.capacity is None or self.seats:
                raise ValueError("General requires capacity without seats")
        elif self.capacity is not None or not self.seats:
            raise ValueError("Numbered requires seats without capacity")
        if len({seat.label for seat in self.seats}) != len(self.seats):
            raise ValueError("Seat labels must be unique")
        return self


class DraftOwnerVerifier:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.url = valid_service_url(settings.events_service_url)
        self.transport = transport

    def require_owner_draft(
        self, event_id: UUID, access_token: str, request_id: str | None,
    ) -> None:
        headers = {"Authorization": f"Bearer {access_token}"}
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            with httpx.Client(
                transport=self.transport, timeout=settings.purchase_timeout_seconds,
                follow_redirects=False, trust_env=False,
            ) as client:
                response = client.get(
                    self.url + f"/api/v1/owner/events/{event_id}/sale-gate-readiness",
                    headers=headers,
                )
        except httpx.RequestError as error:
            raise HTTPException(503, "Events verification unavailable", headers=NO_STORE) from error
        if response.status_code in {401, 403}:
            raise HTTPException(response.status_code, "Access denied", headers=NO_STORE)
        if response.status_code == 404:
            raise HTTPException(404, "Draft event unavailable", headers=NO_STORE)
        if response.status_code != 200:
            raise HTTPException(503, "Events verification unavailable", headers=NO_STORE)
        try:
            result = response.json()
            authorized = (
                isinstance(result, dict)
                and result.get("event_id") == str(event_id)
                and result.get("status") == "draft"
                and result.get("ready_for_gate_provisioning") is True
            )
        except ValueError:
            authorized = False
        if not authorized:
            raise HTTPException(503, "Invalid Events verification response", headers=NO_STORE)


def draft_verifier() -> DraftOwnerVerifier:
    try:
        return DraftOwnerVerifier()
    except ValueError as error:
        raise HTTPException(503, "Events integration unavailable", headers=NO_STORE) from error


def insert_zone(db: Session, event_id: UUID, payload: ZoneInput) -> ZoneResponse:
    zone_id = uuid4()
    spec = ZoneSpec(
        id=zone_id, event_id=event_id, name=payload.name, mode=payload.mode,
        price_minor=payload.price_minor, currency=payload.currency,
        capacity=payload.capacity,
        available=payload.capacity if payload.mode == "general" else None,
    )
    validate_zone(spec)
    for seat in payload.seats:
        validate_seat(SeatSpec(uuid4(), zone_id, seat.label))
    # Gate lock serializes local changes against new purchases and gate transitions.
    # If gate does not exist yet the zone stays unsellable until provisioned.
    gate = db.scalar(
        select(SaleGateRow).where(SaleGateRow.event_id == event_id).with_for_update()
    )
    if gate is not None and gate.state != "closed":
        raise HTTPException(409, "Event sales already open", headers=NO_STORE)
    zone = ZoneRow(
        id=zone_id, event_id=event_id, name=payload.name, mode=payload.mode,
        price_minor=payload.price_minor, currency=payload.currency,
        capacity=payload.capacity, available=spec.available,
    )
    db.add(zone)
    rows = [
        SeatRow(id=uuid4(), zone_id=zone_id, mode="numbered", label=seat.label)
        for seat in payload.seats
    ]
    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Zone conflicts with existing inventory", headers=NO_STORE) from error
    return ZoneResponse(
        id=zone_id, name=payload.name, mode=payload.mode,
        price_minor=payload.price_minor, currency=payload.currency,
        capacity=payload.capacity,
        available=payload.capacity if payload.capacity is not None else len(rows),
        seats=[SeatResponse(id=row.id, label=row.label, available=True) for row in rows],
    )


@router.post("/events/{event_id}/zones", response_model=ZoneResponse, status_code=201)
def create_zone(
    event_id: UUID,
    payload: ZoneInput,
    request: Request,
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verified: Annotated[DraftOwnerVerifier, Depends(draft_verifier)],
    db: Annotated[Session, Depends(inventory_session)],
):
    if not settings.zone_configuration_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE)
    verified.require_owner_draft(
        event_id, credentials.credentials, request.headers.get("X-Request-ID"),
    )
    result = insert_zone(db, event_id, payload)
    response.headers["Cache-Control"] = "no-store"
    return result
