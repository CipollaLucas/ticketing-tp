"""Application-level tests use fake ports, not FastAPI/SQLAlchemy."""
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.ticketing_core.application.ports import OrderRecord
from app.ticketing_core.application.purchase_tickets import purchase_tickets
from app.ticketing_core.domain.purchase import (
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
)

CUSTOMER = UUID("00000000-0000-0000-0000-000000000001")
EVENT = UUID("00000000-0000-0000-0000-000000000002")
ZONE = UUID("00000000-0000-0000-0000-000000000003")
ORDER = UUID("00000000-0000-0000-0000-000000000004")
INTENT = PurchaseIntent(EVENT, (TicketSelection(ZONE, 1),))


class FakeUnitOfWork:
    def __init__(self, existing=False, hash_override=None, fail=False):
        self.previous = (ORDER, hash_override or INTENT.canonical_hash()) if existing else None
        self.fail = fail
        self.calls = []
        self.receipt = OrderRecord(
            ORDER, CUSTOMER, EVENT, "confirmed", 150000, "ARS",
            datetime(2026, 11, 24, tzinfo=UTC), (), (),
        )

    def lock_customer(self, customer_id):
        self.calls.append("lock")

    def find_existing(self, customer_id, key):
        self.calls.append("find")
        return self.previous

    def allocate(self, customer_id, key, intent):
        self.calls.append("allocate")
        if self.fail:
            raise RuntimeError("persist failed")
        return ORDER

    def read_order(self, order_id):
        self.calls.append("read")
        return self.receipt

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")


def test_new_purchase_stays_in_one_transaction():
    fake = FakeUnitOfWork()
    result = purchase_tickets(INTENT, CUSTOMER, "key", fake)
    assert result.order.id == ORDER and result.replayed is False
    assert fake.calls == ["lock", "find", "allocate", "read", "commit"]


def test_replayed_purchase_skips_allocation():
    fake = FakeUnitOfWork(existing=True)
    result = purchase_tickets(INTENT, CUSTOMER, "key", fake)
    assert result.replayed is True
    assert fake.calls == ["lock", "find", "read", "commit"]


def test_changed_payload_rejected_before_any_writes():
    fake = FakeUnitOfWork(existing=True, hash_override="incorrect")
    with pytest.raises(PurchaseKeyConflict):
        purchase_tickets(INTENT, CUSTOMER, "key", fake)
    assert fake.calls == ["lock", "find", "rollback"]


def test_persistence_failure_rolls_back_without_commit():
    fake = FakeUnitOfWork(fail=True)
    with pytest.raises(RuntimeError, match="persist failed"):
        purchase_tickets(INTENT, CUSTOMER, "key", fake)
    assert fake.calls == ["lock", "find", "allocate", "rollback"]
