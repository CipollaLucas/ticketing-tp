"""Isolated business rule tests: no FastAPI, database or SQLAlchemy fixtures."""
from uuid import UUID

import pytest

from app.ticketing_core.domain.purchase import (
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
    assert_replay_compatible,
)


def test_purchase_identity_is_stable_across_item_and_seat_order():
    event = UUID("00000000-0000-0000-0000-000000000001")
    zone_a = UUID("00000000-0000-0000-0000-000000000002")
    zone_b = UUID("00000000-0000-0000-0000-000000000003")
    seats = (
        UUID("00000000-0000-0000-0000-000000000004"),
        UUID("00000000-0000-0000-0000-000000000005"),
    )
    first = PurchaseIntent(event, (
        TicketSelection(zone_b, 2, seats),
        TicketSelection(zone_a, 1),
    ))
    second = PurchaseIntent(event, (
        TicketSelection(zone_a, 1),
        TicketSelection(zone_b, 2, tuple(reversed(seats))),
    ))
    assert first.canonical_hash() == second.canonical_hash()


def test_purchase_identity_changes_with_quantity_event_and_seat():
    event = UUID("00000000-0000-0000-0000-000000000001")
    other_event = UUID("00000000-0000-0000-0000-000000000009")
    zone = UUID("00000000-0000-0000-0000-000000000002")
    seat = UUID("00000000-0000-0000-0000-000000000004")
    base = PurchaseIntent(event, (TicketSelection(zone, 1),))
    assert base.canonical_hash() != PurchaseIntent(
        event, (TicketSelection(zone, 2),),
    ).canonical_hash()
    assert base.canonical_hash() != PurchaseIntent(
        other_event, (TicketSelection(zone, 1),),
    ).canonical_hash()
    assert base.canonical_hash() != PurchaseIntent(
        event, (TicketSelection(zone, 1, (seat,)),),
    ).canonical_hash()


def test_idempotency_replay_requires_identical_hash():
    assert_replay_compatible("same", "same")
    with pytest.raises(PurchaseKeyConflict, match="another payload"):
        assert_replay_compatible("old", "new")
