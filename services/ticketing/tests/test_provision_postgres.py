"""Real disposable PostgreSQL concurrency and no-reset regression."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command
from ticketing_service.persistence import SaleGateRow
from ticketing_service.provision import provision_closed_gate
from ticketing_service.provision_persistence import SqlAlchemyGateProvisionUnitOfWork

URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Disposable PostgreSQL not configured")


def test_gate_created_closed_then_repeat_preserves_open_gate():
    assert URL is not None
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(URL)
    event_id = uuid4()
    with Session(engine) as db:
        assert (
            provision_closed_gate(
                event_id,
                SqlAlchemyGateProvisionUnitOfWork(db),
            ).state
            == "closed"
        )
    with Session(engine) as db:
        gate = db.get(SaleGateRow, event_id)
        assert gate is not None
        gate.state = "open"
        gate.version = 4
        gate.event_revision = 5
        db.commit()
    with Session(engine) as db:
        result = provision_closed_gate(event_id, SqlAlchemyGateProvisionUnitOfWork(db))
    assert (result.state, result.version, result.event_revision) == ("open", 4, 5)
    engine.dispose()


def test_parallel_provision_creates_one_closed_gate():
    assert URL is not None
    engine = create_engine(URL, pool_size=4)
    event_id = uuid4()

    def provision_once():
        with Session(engine) as db:
            return provision_closed_gate(event_id, SqlAlchemyGateProvisionUnitOfWork(db))

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: provision_once(), range(3)))
    assert all((item.state, item.version) == ("closed", 0) for item in results)
    with Session(engine) as db:
        assert db.get(SaleGateRow, event_id).state == "closed"
    engine.dispose()
