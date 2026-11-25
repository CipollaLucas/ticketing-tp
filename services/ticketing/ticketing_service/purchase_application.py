"""Purchase orchestration: one UoW for idempotency, gate, stock, order and tickets.

No customer-role or Event metadata is looked up through SQL. The inbound
adapter, when implemented, MUST verify Identity and relevant Events contract
before calling this use case. No purchase HTTP endpoint is enabled.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from ticketing_service.purchase import (
    PurchaseIntent,
    PurchaseKeyConflict,
    validate_purchase,
)


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


@dataclass(frozen=True)
class PurchaseOutcome:
    order: OrderRecord
    replayed: bool


class PurchaseUnitOfWork(Protocol):
    def lock_customer_key(self, customer_id: UUID) -> None: ...
    def find_existing(self, customer_id: UUID, key: str) -> tuple[UUID, str] | None: ...
    def allocate(self, customer_id: UUID, key: str, intent: PurchaseIntent) -> UUID: ...
    def read_order(self, order_id: UUID) -> OrderRecord: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def purchase_tickets(
    intent: PurchaseIntent, customer_id: UUID, key: str, unit: PurchaseUnitOfWork,
) -> PurchaseOutcome:
    """Idempotent historical replay is allowed after sale gate is closed."""
    validate_purchase(intent, key)
    try:
        unit.lock_customer_key(customer_id)
        existing = unit.find_existing(customer_id, key)
        if existing:
            order_id, stored_hash = existing
            if stored_hash != intent.canonical_hash():
                raise PurchaseKeyConflict("Idempotency key used for another payload")
            outcome = PurchaseOutcome(unit.read_order(order_id), replayed=True)
        else:
            order_id = unit.allocate(customer_id, key, intent)
            outcome = PurchaseOutcome(unit.read_order(order_id), replayed=False)
        unit.commit()
        return outcome
    except Exception:
        unit.rollback()
        raise


def replay_confirmed_purchase(
    intent: PurchaseIntent, customer_id: UUID, key: str, unit: PurchaseUnitOfWork,
) -> PurchaseOutcome | None:
    """Look up a verified customer's prior purchase without consulting Events.

    Never creates orders or touches the sale gate. The customer-scoped advisory
    lock serializes this read against a concurrent purchase using the same key.
    A missing record is NOT a purchase authorization; the caller must check
    the public Events admission before invoking purchase_tickets.
    """
    validate_purchase(intent, key)
    try:
        unit.lock_customer_key(customer_id)
        prior = unit.find_existing(customer_id, key)
        if prior is None:
            unit.rollback()
            return None
        order_id, stored_hash = prior
        if stored_hash != intent.canonical_hash():
            raise PurchaseKeyConflict("Idempotency key used for another payload")
        result = PurchaseOutcome(unit.read_order(order_id), replayed=True)
        unit.commit()
        return result
    except Exception:
        unit.rollback()
        raise
