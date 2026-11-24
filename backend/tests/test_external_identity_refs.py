"""Migration removes only cross-context user FKs while preserving all data."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session
from test_postgres import postgres_engine as postgres_engine  # noqa: PLC0414

from alembic import command
from app.models import Event, Order, User, Zone

TEST_USER = "legacy_owner_for_migration"


@pytest.mark.parametrize("database", ["sqlite", "postgres"])
def test_external_user_references_migration_roundtrip(database, request, tmp_path):
    if database == "postgres":
        engine = request.getfixturevalue("postgres_engine")
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'external-identity.db'}")

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0004_purchasing")

    with Session(engine) as db:
        user = User(
            username=TEST_USER, display_name="Legacy Owner",
            role="event_owner", password_hash="unused",
        )
        db.add(user)
        db.flush()
        start = datetime.now(UTC) + timedelta(days=7)
        meeting = Event(
            owner_id=user.id, name="Existing event", description="preserve",
            venue="Hall", start_at=start, end_at=start + timedelta(hours=2),
        )
        db.add(meeting)
        db.flush()
        zone = Zone(
            event_id=meeting.id, name="General", mode="general",
            price_minor=100, currency="ARS", capacity=3, available=3,
        )
        db.add(zone)
        db.flush()
        order = Order(
            customer_id=user.id, event_id=meeting.id, idempotency_key="keep",
            request_hash="a" * 64, total_minor=100, currency="ARS",
        )
        db.add(order)
        db.commit()
        user_id, event_id, order_id = user.id, meeting.id, order.id

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert not any(
            fk["referred_table"] == "users"
            for table in ("events", "orders")
            for fk in inspect(connection).get_foreign_keys(table)
        )
        assert any(
            fk["referred_table"] == "users"
            for fk in inspect(connection).get_foreign_keys("auth_sessions")
        )
    with Session(engine) as db:
        assert db.get(Event, event_id).owner_id == user_id
        assert db.get(Order, order_id).customer_id == user_id
        external_id = uuid4()
        db.add(Event(
            owner_id=external_id, name="External identity",
            description="reference only", venue="Hall",
            start_at=start, end_at=start + timedelta(hours=2),
        ))
        db.commit()
        # A runtime call must still validate owner/customer through Identity
        # before writing. This test intentionally proves FK decoupling only.
        db.query(Event).filter(Event.owner_id == external_id).delete()
        db.commit()

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0004_purchasing")
        assert any(
            fk["referred_table"] == "users"
            for table in ("events", "orders")
            for fk in inspect(connection).get_foreign_keys(table)
        )
    with Session(engine) as db:
        assert db.get(Event, event_id).owner_id == user_id
        assert db.get(Order, order_id).customer_id == user_id
        assert db.get(User, user_id).username == TEST_USER
    if database == "sqlite":
        engine.dispose()
