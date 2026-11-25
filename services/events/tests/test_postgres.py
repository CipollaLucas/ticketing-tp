"""Real DB integration only when TEST_POSTGRES_URL points to disposable PostgreSQL."""
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

from alembic import command
from events_service.application import public_catalog
from events_service.persistence import EventRow, SqlAlchemyEventReader


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Dedicated PostgreSQL not configured")
def test_independent_postgres_migration_roundtrip():
    # CI provides an entirely disposable PostgreSQL database, not a shared DB.
    url = os.environ["TEST_POSTGRES_URL"]
    engine = create_engine(url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
            assert set(inspect(connection).get_table_names()) == {"alembic_version", "events", "event_publication_intents"}
            assert len(inspect(connection).get_foreign_keys("events")) == 0
        now = datetime.now(UTC)
        with Session(engine) as db:
            db.add(EventRow(
                id=uuid4(), owner_id=uuid4(), name="PostgreSQL event",
                description="Independent", venue="Venue",
                start_at=now + timedelta(days=1),
                end_at=now + timedelta(days=2), status="published",
            ))
            db.commit()
            rows, count = public_catalog(SqlAlchemyEventReader(db), now)
            assert count == len(rows) == 1
            assert db.scalar(select(func.count()).select_from(EventRow)) == 1
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
            connection.commit()
            assert "events" not in inspect(connection).get_table_names()
    finally:
        engine.dispose()
