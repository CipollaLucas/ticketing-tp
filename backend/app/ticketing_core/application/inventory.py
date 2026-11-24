"""Framework-free inventory use cases and contracts."""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ZoneCommand:
    name: str
    mode: str
    price_minor: int
    currency: str
    capacity: int | None
    seats: tuple[str, ...]


@dataclass(frozen=True)
class SeatView:
    id: UUID
    label: str
    available: bool


@dataclass(frozen=True)
class ZoneView:
    id: UUID
    name: str
    mode: str
    price_minor: int
    currency: str
    capacity: int | None
    available: int
    seats: tuple[SeatView, ...]


@dataclass(frozen=True)
class InventoryView:
    event_id: UUID
    zones: tuple[ZoneView, ...]


class InventoryPort(Protocol):
    def add_zone(self, event_id: UUID, actor_id: UUID, command: ZoneCommand) -> UUID: ...
    def read_zone(self, zone_id: UUID) -> ZoneView: ...
    def read_inventory(self, event_id: UUID, actor_id: UUID | None) -> InventoryView: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def configure_zone(
    event_id: UUID, actor_id: UUID, command: ZoneCommand, port: InventoryPort,
) -> ZoneView:
    try:
        zone_id = port.add_zone(event_id, actor_id, command)
        port.commit()
        return port.read_zone(zone_id)
    except Exception:
        port.rollback()
        raise


def view_inventory(
    event_id: UUID, actor_id: UUID | None, port: InventoryPort,
) -> InventoryView:
    return port.read_inventory(event_id, actor_id)
