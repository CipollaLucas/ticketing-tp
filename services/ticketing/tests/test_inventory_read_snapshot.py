"""Read-only snapshot uses only Ticketing-owned data and sold seat rows."""
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ticketing_service.inventory_http import inventory_snapshot
from ticketing_service.persistence import (
    Base,
    OrderItemRow,
    OrderRow,
    SeatRow,
    TicketRow,
    ZoneRow,
)


def test_inventory_snapshot_general_numbered_and_sold_seats():
    db_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(db_engine)
    event_id = uuid4()
    general_id, numbered_id = uuid4(), uuid4()
    free_seat, sold_seat = uuid4(), uuid4()
    order_id, item_id = uuid4(), uuid4()
    with Session(db_engine) as db:
        db.add_all([
            ZoneRow(
                id=general_id, event_id=event_id, name="General",
                mode="general", price_minor=2500, currency="ARS",
                capacity=10, available=7,
            ),
            ZoneRow(
                id=numbered_id, event_id=event_id, name="VIP",
                mode="numbered", price_minor=5500, currency="ARS",
                capacity=None, available=None,
            ),
        ])
        db.flush()
        db.add_all([
            SeatRow(id=free_seat, zone_id=numbered_id, mode="numbered", label="A2"),
            SeatRow(id=sold_seat, zone_id=numbered_id, mode="numbered", label="A1"),
            OrderRow(
                id=order_id, customer_id=uuid4(), event_id=event_id,
                idempotency_key="sold-seat", request_hash="0" * 64,
                total_minor=5500, currency="ARS", status="confirmed",
                created_at=datetime.now(UTC),
            ),
        ])
        db.flush()
        db.add(OrderItemRow(
            id=item_id, order_id=order_id, zone_id=numbered_id,
            quantity=1, unit_price_minor=5500, subtotal_minor=5500,
        ))
        db.flush()
        db.add(TicketRow(
            id=uuid4(), order_item_id=item_id, zone_id=numbered_id,
            seat_id=sold_seat, status="valid",
        ))
        db.commit()

        result = inventory_snapshot(db, event_id)
        assert result.event_id == event_id
        assert len(result.zones) == 2
        general, vip = result.zones
        assert general.name == "General"
        assert general.available == 7 and general.capacity == 10
        assert general.seats == []
        assert vip.name == "VIP"
        assert vip.capacity is None and vip.available == 1
        assert [(s.label, s.available) for s in vip.seats] == [
            ("A1", False), ("A2", True),
        ]
    db_engine.dispose()
