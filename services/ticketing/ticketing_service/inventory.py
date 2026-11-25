"""Pure Ticketing inventory validation; no ORM or service-to-service imports."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ZoneMode = Literal["general", "numbered"]


@dataclass(frozen=True)
class ZoneSpec:
    id: UUID
    event_id: UUID
    name: str
    mode: ZoneMode
    price_minor: int
    currency: str
    capacity: int | None
    available: int | None


@dataclass(frozen=True)
class SeatSpec:
    id: UUID
    zone_id: UUID
    label: str


def validate_zone(zone: ZoneSpec) -> None:
    if not 1 <= len(zone.name.strip()) <= 100:
        raise ValueError("Zone name must be between 1 and 100 characters")
    if zone.mode not in ("general", "numbered"):
        raise ValueError("Invalid zone mode")
    if not 0 <= zone.price_minor <= 2_147_483_647:
        raise ValueError("Invalid zone price")
    if zone.currency not in ("ARS", "USD", "EUR"):
        raise ValueError("Invalid currency")
    if zone.mode == "general":
        if zone.capacity is None or zone.available is None:
            raise ValueError("General admission requires capacity and availability")
        if not 1 <= zone.capacity <= 1_000_000 or not 0 <= zone.available <= zone.capacity:
            raise ValueError("Invalid general admission capacity")
    elif zone.capacity is not None or zone.available is not None:
        raise ValueError("Numbered zone must not track aggregate capacity")


def validate_seat(seat: SeatSpec) -> None:
    if not 1 <= len(seat.label.strip()) <= 50:
        raise ValueError("Seat label must be between 1 and 50 characters")
