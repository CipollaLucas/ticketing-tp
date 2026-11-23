"""Migration contracts shared by SQLite and real PostgreSQL checks."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, event, insert, inspect, select
from sqlalchemy.exc import DataError, IntegrityError

from alembic import command
from app.database import Base
from app.models import Event, User


def assert_event_migration(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    user_id, event_id = uuid4(), uuid4()
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_identity")
        connection.execute(insert(User).values(
            id=user_id, username="migration_owner", display_name="Owner",
            password_hash="unused", role="event_owner",
        ))
        connection.commit()
        command.upgrade(config, "head")
        assert "events" in inspect(connection).get_table_names()
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        start = datetime.now(UTC) + timedelta(days=5)
        values = {
            "id": event_id, "owner_id": user_id, "name": "Concert", "description": "Music",
            "venue": "Hall", "start_at": start, "end_at": start + timedelta(hours=2),
            "status": "draft",
        }
        connection.execute(insert(Event).values(**values))
        connection.commit()
        assert connection.scalar(select(Event.name).where(Event.id == event_id)) == "Concert"
        for invalid in (
            {"status": "invalid"}, {"name": " "}, {"venue": ""},
            {"end_at": start}, {"owner_id": uuid4()}, {"description": "x" * 5001},
        ):
            with pytest.raises((IntegrityError, DataError)), connection.begin_nested():
                connection.execute(insert(Event).values(**{**values, "id": uuid4(), **invalid}))
        connection.commit()
        command.downgrade(config, "0001_identity")
        assert "events" not in inspect(connection).get_table_names()
        assert connection.scalar(select(User.username).where(User.id == user_id)) == "migration_owner"
        connection.commit()
        command.upgrade(config, "head")
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert connection.scalar(select(User.id)) == user_id


def test_event_migration_preserves_identity_and_enforces_constraints(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        assert_event_migration(engine)
    finally:
        engine.dispose()
