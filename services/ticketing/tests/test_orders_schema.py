"""PostgreSQL-only integrity checks on a disposable Ticketing database."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from ticketing_service.persistence import OrderItemRow, OrderRow, TicketRow, ZoneRow

DB_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="Disposable PostgreSQL not configured")


def test_orders_schema_has_no_external_user_or_event_foreign_key():
    assert DB_URL is not None
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    assert {"orders", "order_items", "tickets"} <= set(inspector.get_table_names())
    assert inspector.get_foreign_keys("orders") == []
    assert {row["referred_table"] for row in inspector.get_foreign_keys("order_items")} == {
        "orders",
        "zones",
    }
    assert {row["referred_table"] for row in inspector.get_foreign_keys("tickets")} == {
        "order_items",
        "seats",
        "zones",
    }
    engine.dispose()


def test_idempotency_and_ticket_zone_integrity_are_database_enforced():
    assert DB_URL is not None
    engine = create_engine(DB_URL)
    event_id, customer_id, zone_id, order_id, item_id = (uuid4() for _ in range(5))
    with Session(engine) as db:
        db.add(
            ZoneRow(
                id=zone_id,
                event_id=event_id,
                name="Order schema fixture",
                mode="general",
                price_minor=1000,
                currency="ARS",
                capacity=10,
                available=10,
            )
        )
        db.add(
            OrderRow(
                id=order_id,
                customer_id=customer_id,
                event_id=event_id,
                idempotency_key="schema-fixture-key",
                request_hash="a" * 64,
                total_minor=2000,
                currency="ARS",
                status="confirmed",
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    with Session(engine) as db:
        db.add(
            OrderItemRow(
                id=item_id,
                order_id=order_id,
                zone_id=zone_id,
                quantity=2,
                unit_price_minor=1000,
                subtotal_minor=2000,
            )
        )
        db.commit()
    with Session(engine) as db:
        db.add(
            TicketRow(
                id=uuid4(),
                order_item_id=item_id,
                zone_id=zone_id,
                seat_id=None,
                status="valid",
            )
        )
        db.commit()
    with Session(engine) as db, pytest.raises(IntegrityError):
        db.add(
            OrderRow(
                id=uuid4(),
                customer_id=customer_id,
                event_id=event_id,
                idempotency_key="schema-fixture-key",
                request_hash="b" * 64,
                total_minor=2000,
                currency="ARS",
                status="confirmed",
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
    with Session(engine) as db, pytest.raises(IntegrityError):
        db.add(
            OrderItemRow(
                id=uuid4(),
                order_id=order_id,
                zone_id=zone_id,
                quantity=2,
                unit_price_minor=1000,
                subtotal_minor=1999,
            )
        )
        db.commit()
    engine.dispose()
