"""Ports owned by Ticketing application; no ORM, FastAPI, or HTTP dependencies."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.ticketing_core.domain.purchase import PurchaseIntent


class PurchaseError(Exception):
    """Application error translated to HTTP only at the inbound edge."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class TicketRecord:
    id: UUID
    order_item_id: UUID
    zone_id: UUID
    seat_id: UUID | None
    status: str


@dataclass(frozen=True)
class OrderLineRecord:
    id: UUID
    zone_id: UUID
    quantity: int
    unit_price_minor: int
    subtotal_minor: int


@dataclass(frozen=True)
class OrderRecord:
    id: UUID
    customer_id: UUID
    event_id: UUID
    status: str
    total_minor: int
    currency: str
    created_at: datetime
    items: tuple[OrderLineRecord, ...]
    tickets: tuple[TicketRecord, ...]


class PurchaseUnitOfWorkPort(Protocol):
    def lock_customer(self, customer_id: UUID) -> None:
        """Lock and revalidate the customer role before checking idempotency."""
        ...

    def find_existing(self, customer_id: UUID, key: str) -> tuple[UUID, str] | None:
        """Read (order_id, canonical_hash) for an already completed purchase."""
        ...

    def allocate(self, customer_id: UUID, key: str, intent: PurchaseIntent) -> UUID:
        """Lock inventory, allocate it and create a complete order atomically."""
        ...

    def read_order(self, order_id: UUID) -> OrderRecord:
        """Read receipt before commit so all writes roll back together on failure."""
        ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
