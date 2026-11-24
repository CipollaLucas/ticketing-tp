from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_postgres import postgres_engine as postgres_engine  # noqa: PLC0414

from alembic import command
from app.auth import token_digest
from app.database import Base, get_db
from app.inventory import router
from app.models import AuthSession, Event, Seat, User, Zone


def seed_inventory(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as db:
        owner = User(username="inventory_owner", display_name="Owner", password_hash="unused",
                     role="event_owner")
        db.add(owner)
        db.flush()
        start = datetime.now(UTC) + timedelta(days=10)
        event = Event(owner_id=owner.id, name="Concert", description="Music", venue="Hall",
                      start_at=start, end_at=start + timedelta(hours=2), status="draft")
        db.add(event)
        db.add(AuthSession(token_hash=token_digest("inventory-token"), user_id=owner.id,
                           expires_at=datetime.now(UTC) + timedelta(hours=1)))
        db.commit()
        return event.id


def test_inventory_postgres_concurrent_duplicate(postgres_engine):
    eid = seed_inventory(postgres_engine)
    app = FastAPI()
    app.include_router(router)
    barrier = Barrier(2)

    def test_db():
        with Session(postgres_engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db

    def create(_):
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            return client.post(f"/api/v1/events/{eid}/zones",
                headers={"Authorization": "Bearer inventory-token"},
                json={"name": "Campo", "mode": "general", "capacity": 1,
                      "price_minor": 100, "currency": "ARS"}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(create, range(2))) == [201, 409]
    with Session(postgres_engine) as db:
        assert len(db.scalars(select(Zone)).all()) == 1


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_inventory_migrations_and_constraints(backend, request, tmp_path):
    engine = request.getfixturevalue("postgres_engine") if backend == "postgres" else create_engine(
        f"sqlite:///{tmp_path / 'inventory.db'}")
    if backend == "sqlite":
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    eid = seed_inventory(engine)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        connection.rollback()
        # Round-trip new migration, preserving users/events.
        command.downgrade(config, "0002_events")
        command.upgrade(config, "head")
    with Session(engine) as db:
        for changes in [{"capacity": 0}, {"available": -1}, {"available": 3},
                        {"currency": "BAD"}, {"price_minor": -1}]:
            with pytest.raises(IntegrityError):
                db.add(Zone(id=uuid4(), event_id=eid, **{
                    "name": "Invalid", "mode": "general", "capacity": 2, "available": 2,
                    "price_minor": 100, "currency": "ARS", **changes}))
                db.commit()
            db.rollback()
        zone = Zone(event_id=eid, name="General", mode="general", capacity=1, available=1,
                    price_minor=0, currency="ARS")
        db.add(zone)
        db.commit()
        with pytest.raises(IntegrityError):
            db.add(Seat(zone_id=zone.id, label="A1"))
            db.commit()
        db.rollback()
    if backend == "sqlite":
        engine.dispose()
