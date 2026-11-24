"""Domain policy for purchase identity, canonical requests and replay conflicts.

Pure Python: deliberately does not import FastAPI, Pydantic, or SQLAlchemy.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID


class PurchaseKeyConflict(Exception):
    """An idempotency key cannot represent two different purchase intentions."""


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
        """Identity excludes client-supplied prices and ignores item/seat order."""
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


def assert_replay_compatible(stored_hash: str, requested_hash: str) -> None:
    """Reject reuse of the same idempotency key with a different payload."""
    if stored_hash != requested_hash:
        raise PurchaseKeyConflict("Idempotency key used for another payload")
