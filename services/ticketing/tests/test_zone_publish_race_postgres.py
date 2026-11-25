"""PostgreSQL isolation proof: gate opening and zone creation share row locking.

Only disposable TEST_POSTGRES_URL databases are accepted; skipped otherwise.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ticketing_service.persistence import SaleGateRow, ZoneRow
from ticketing_service.zone_configuration_http import ZoneInput, insert_zone

URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Disposable PostgreSQL not configured")


def test_gate_open_wins_over_zone_creation_without_reset():
    assert URL is not None
    engine = create_engine(URL, pool_size=3)
    event_id = uuid4()
    publisher_locked = Event()
    release_publisher = Event()
    payload = ZoneInput(
        name="Blocked Zone", mode="general", price_minor=1000,
        currency="ARS", capacity=2,
    )
    with Session(engine) as db:
        db.add(SaleGateRow(event_id=event_id, state="closed", version=0, event_revision=0))
        db.commit()

    def opener() -> None:
        with Session(engine) as db:
            gate = db.scalar(
                select(SaleGateRow)
                .where(SaleGateRow.event_id == event_id)
                .with_for_update()
            )
            assert gate is not None and gate.state == "closed"
            publisher_locked.set()
            assert release_publisher.wait(timeout=10)
            gate.state = "open"
            gate.version = 1
            gate.event_revision = 1
            db.commit()

    def zone_writer() -> int:
        with Session(engine) as db:
            try:
                insert_zone(db, event_id, payload)
            except Exception as error:
                from fastapi import HTTPException

                if isinstance(error, HTTPException):
                    db.rollback()
                    return error.status_code
                raise
        return 201

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            opened = pool.submit(opener)
            assert publisher_locked.wait(timeout=10)
            written = pool.submit(zone_writer)
            release_publisher.set()
            opened.result(timeout=15)
            assert written.result(timeout=15) == 409

        with Session(engine) as db:
            gate = db.get(SaleGateRow, event_id)
            assert gate is not None
            assert (gate.state, gate.version, gate.event_revision) == ("open", 1, 1)
            assert db.scalars(select(ZoneRow).where(ZoneRow.event_id == event_id)).all() == []
    finally:
        release_publisher.set()
        engine.dispose()
