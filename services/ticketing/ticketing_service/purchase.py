"""Pure purchase identity and validation; canonical hash matches Legacy."""
import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID


class PurchaseKeyConflict(Exception):
    """The same idempotency key cannot be used for a different purchase."""


class PurchaseError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class TicketSelection:
    zone_id: UUID
    quantity: int
    seat_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class PurchaseIntent:
    event_id: UUID
    items: tuple[TicketSelection, ...]

    def canonical_hash(self) -> str:
        data = {
            "event_id": str(self.event_id),
            "items": [
                {
                    "zone_id": str(item.zone_id),
                    "quantity": item.quantity,
                    "seat_ids": sorted(str(seat) for seat in item.seat_ids),
                }
                for item in sorted(self.items, key=lambda item: item.zone_id)
            ],
        }
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()


def validate_purchase(intent: PurchaseIntent, key: str) -> None:
    if not 1 <= len(key) <= 128 or any(not 33 <= ord(c) <= 126 for c in key):
        raise PurchaseError(422, "Invalid idempotency key")
    if not 1 <= len(intent.items) <= 20:
        raise PurchaseError(422, "At least one and at most twenty zones required")
    if len({item.zone_id for item in intent.items}) != len(intent.items):
        raise PurchaseError(422, "Zones must be unique")
    seats = [seat for item in intent.items for seat in item.seat_ids]
    if len(seats) != len(set(seats)):
        raise PurchaseError(422, "Seats must be unique")
    if sum(item.quantity for item in intent.items) > 100:
        raise PurchaseError(422, "At most one hundred tickets")
    if any(
        item.quantity < 1 or item.quantity > 100 or len(item.seat_ids) > 100
        for item in intent.items
    ):
        raise PurchaseError(422, "Invalid ticket quantity")
