"""Ticketing-owned schema contract. PostgreSQL CI proves real constraints."""

import os
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from ticketing_service.persistence import SeatRow, ZoneRow

DB_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="Disposable PostgreSQL not configured")


def test_inventory_migration_and_no_cross_context_foreign_keys():
    assert DB_URL is not None
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(DB_URL)
    schema = inspect(engine)
    assert {"zones", "seats", "sale_gates", "sale_gate_commands"} <= set(schema.get_table_names())
    assert schema.get_foreign_keys("zones") == []  # Events lives elsewhere.
    assert {tuple(fk["constrained_columns"]) for fk in schema.get_foreign_keys("seats")} == {
        ("zone_id", "mode"),
    }
    assert schema.get_foreign_keys("seats")[0]["referred_table"] == "zones"
    engine.dispose()


def test_numbered_seat_and_general_stock_constraints():
    assert DB_URL is not None
    engine = create_engine(DB_URL)
    event_id, general_id, numbered_id = uuid4(), uuid4(), uuid4()
    with Session(engine) as db:
        db.add_all(
            [
                ZoneRow(
                    id=general_id,
                    event_id=event_id,
                    name="General",
                    mode="general",
                    price_minor=2500,
                    currency="ARS",
                    capacity=100,
                    available=100,
                ),
                ZoneRow(
                    id=numbered_id,
                    event_id=event_id,
                    name="VIP",
                    mode="numbered",
                    price_minor=3500,
                    currency="ARS",
                    capacity=None,
                    available=None,
                ),
            ]
        )
        db.commit()
    with Session(engine) as db:
        db.add(SeatRow(id=uuid4(), zone_id=numbered_id, mode="numbered", label="A1"))
        db.commit()
    with Session(engine) as db, pytest.raises(IntegrityError):
        db.add(SeatRow(id=uuid4(), zone_id=general_id, mode="numbered", label="A1"))
        db.commit()
    with Session(engine) as db, pytest.raises(IntegrityError):
        db.add(
            ZoneRow(
                id=uuid4(),
                event_id=event_id,
                name="Invalid",
                mode="general",
                price_minor=100,
                currency="ARS",
                capacity=10,
                available=11,
            )
        )
        db.commit()
    with Session(engine) as db:
        rows = db.scalars(select(ZoneRow).where(ZoneRow.event_id == event_id)).all()
        assert len(rows) == 2
        assert db.scalars(select(SeatRow).where(SeatRow.zone_id == numbered_id)).one().label == "A1"
    engine.dispose()
