"""Real PostgreSQL integration only against ephemeral CI TEST_POSTGRES_URL.

Never run this test with a non-disposable database.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from alembic import command
from ticketing_service.application import change_sale_gate
from ticketing_service.domain import GateCommand, GateConflict
from ticketing_service.persistence import GateCommandRow, SaleGateRow, SqlAlchemyGateUnitOfWork

DB_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="Disposable PostgreSQL not configured")


def test_schema_command_replay_and_stale_version():
    assert DB_URL is not None
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(DB_URL)
    assert {"sale_gates", "sale_gate_commands"} <= set(inspect(engine).get_table_names())
    event = uuid4()
    first = GateCommand(uuid4(), event, "open", 0, 1)
    with Session(engine) as db:
        db.add(SaleGateRow(event_id=event, state="closed", version=0, event_revision=0))
        db.commit()
    with Session(engine) as db:
        assert change_sale_gate(first, SqlAlchemyGateUnitOfWork(db)).version == 1
    with Session(engine) as db:
        assert change_sale_gate(first, SqlAlchemyGateUnitOfWork(db)).version == 1
    with Session(engine) as db:
        with pytest.raises(GateConflict):
            change_sale_gate(GateCommand(uuid4(), event, "close", 0, 1),
                             SqlAlchemyGateUnitOfWork(db))
    with Session(engine) as db:
        assert db.get(SaleGateRow, event).state == "open"
        assert len(db.scalars(select(GateCommandRow).where(
            GateCommandRow.event_id == event
        )).all()) == 1
    engine.dispose()


def test_close_and_gate_lock_share_postgres_row_serialization():
    """Simulates purchase-side gate locking; inventory/order migration still pending."""
    assert DB_URL is not None
    engine = create_engine(DB_URL, pool_size=4, max_overflow=2)
    event = uuid4()
    with Session(engine) as db:
        db.add(SaleGateRow(event_id=event, state="open", version=1, event_revision=1))
        db.commit()
    has_lock = Event()
    release = Event()

    def synthetic_purchase_lock():
        with Session(engine) as db:
            row = db.scalar(select(SaleGateRow).where(
                SaleGateRow.event_id == event
            ).with_for_update())
            assert row is not None and row.state == "open"
            has_lock.set()
            assert release.wait(timeout=10)
            db.commit()

    def close_gate():
        assert has_lock.wait(timeout=10)
        with Session(engine) as db:
            return change_sale_gate(
                GateCommand(uuid4(), event, "close", 1, 1),
                SqlAlchemyGateUnitOfWork(db),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        held = executor.submit(synthetic_purchase_lock)
        closed = executor.submit(close_gate)
        assert has_lock.wait(timeout=10)
        release.set()
        held.result(timeout=15)
        assert closed.result(timeout=15).state == "closed"
    with Session(engine) as db:
        assert db.get(SaleGateRow, event).state == "closed"
    engine.dispose()
