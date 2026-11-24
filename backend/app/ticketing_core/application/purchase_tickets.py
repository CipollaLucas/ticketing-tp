"""Purchase use case: orchestration depends only on a transactional port."""
from dataclasses import dataclass
from uuid import UUID

from app.ticketing_core.application.ports import OrderRecord, PurchaseUnitOfWorkPort
from app.ticketing_core.domain.purchase import (
    PurchaseIntent,
    assert_replay_compatible,
)


@dataclass(frozen=True)
class PurchaseOutcome:
    order: OrderRecord
    replayed: bool


def purchase_tickets(
    intent: PurchaseIntent, customer_id: UUID, idempotency_key: str,
    unit_of_work: PurchaseUnitOfWorkPort,
) -> PurchaseOutcome:
    """All steps share one transaction including the role and event locks."""
    try:
        unit_of_work.lock_customer(customer_id)
        existing = unit_of_work.find_existing(customer_id, idempotency_key)
        if existing:
            order_id, stored_hash = existing
            assert_replay_compatible(stored_hash, intent.canonical_hash())
            outcome = PurchaseOutcome(unit_of_work.read_order(order_id), replayed=True)
        else:
            order_id = unit_of_work.allocate(customer_id, idempotency_key, intent)
            outcome = PurchaseOutcome(unit_of_work.read_order(order_id), replayed=False)
        unit_of_work.commit()
        return outcome
    except Exception:
        unit_of_work.rollback()
        raise
