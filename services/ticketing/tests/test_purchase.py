"""Pure port contract, hashing parity and idempotent replay behavior."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ticketing_service.purchase import (
    PurchaseError,
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
)
from ticketing_service.purchase_application import (
    OrderRecord,
    purchase_tickets,
)


class FakeUnit:
    def __init__(self):
        self.existing = None
        self.allocated = 0
        self.commits = 0
        self.rollbacks = 0
        self.customer_locks = 0
        self.order_id = uuid4()

    def lock_customer_key(self, customer_id):
        self.customer_locks += 1

    def find_existing(self, customer_id, key):
        return self.existing

    def allocate(self, customer_id, key, intent):
        self.allocated += 1
        return self.order_id

    def read_order(self, order_id):
        return OrderRecord(
            order_id,
            uuid4(),
            uuid4(),
            "confirmed",
            100,
            "ARS",
            datetime.now(UTC),
            (),
            (),
        )

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_canonical_hash_matches_legacy_sorting():
    event, zone_a, zone_b, seat_a, seat_b = (uuid4() for _ in range(5))
    first = PurchaseIntent(
        event,
        (
            TicketSelection(zone_a, 2, (seat_a, seat_b)),
            TicketSelection(zone_b, 1),
        ),
    )
    reversed_intent = PurchaseIntent(
        event,
        (
            TicketSelection(zone_b, 1),
            TicketSelection(zone_a, 2, (seat_b, seat_a)),
        ),
    )
    assert first.canonical_hash() == reversed_intent.canonical_hash()
    assert len(first.canonical_hash()) == 64


def test_allocate_and_historical_replay_without_second_allocation():
    intent = PurchaseIntent(uuid4(), (TicketSelection(uuid4(), 1),))
    u = FakeUnit()
    created = purchase_tickets(intent, uuid4(), "one-key", u)
    assert not created.replayed and u.allocated == 1 and u.commits == 1
    u.existing = (created.order.id, intent.canonical_hash())
    replay = purchase_tickets(intent, uuid4(), "one-key", u)
    assert replay.replayed and u.allocated == 1 and u.commits == 2


def test_conflicting_idempotency_key_rolls_back():
    intent = PurchaseIntent(uuid4(), (TicketSelection(uuid4(), 1),))
    u = FakeUnit()
    u.existing = (uuid4(), "wrong-hash")
    with pytest.raises(PurchaseKeyConflict):
        purchase_tickets(intent, uuid4(), "one-key", u)
    assert u.rollbacks == 1 and u.allocated == 0


@pytest.mark.parametrize(
    "intent,key",
    [
        (PurchaseIntent(uuid4(), ()), "one-key"),
        (PurchaseIntent(uuid4(), (TicketSelection(uuid4(), 0),)), "one-key"),
        (PurchaseIntent(uuid4(), (TicketSelection(uuid4(), 101),)), "one-key"),
        (PurchaseIntent(uuid4(), (TicketSelection(uuid4(), 1),)), "bad key"),
        (PurchaseIntent(uuid4(), (TicketSelection(uuid4(), 1),)), ""),
    ],
)
def test_bad_intent_rejected_before_any_db_lock(intent, key):
    u = FakeUnit()
    with pytest.raises(PurchaseError):
        purchase_tickets(intent, uuid4(), key, u)
    assert u.customer_locks == 0 and u.allocated == 0
