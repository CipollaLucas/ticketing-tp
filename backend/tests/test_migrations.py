from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from alembic import command


def test_migrations_round_trip_and_match_models(tmp_path):
    root = Path(__file__).resolve().parents[1]
    assert (root / "alembic.ini").exists(), "Alembic is not configured yet"
    from app import models  # noqa: F401
    from app.database import Base

    config = Config(str(root / "alembic.ini"))
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    config.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    try:
        command.upgrade(config, "head")
        assert {"users", "auth_sessions"} <= set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "base")
        assert not {"users", "auth_sessions"} & set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
        assert {"users", "auth_sessions"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migrated_database_enforces_constraints_and_cascade(tmp_path):
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    import pytest
    from sqlalchemy import delete, event, func, insert, select
    from sqlalchemy.exc import IntegrityError

    from app.models import AuthSession, User

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    url = f"sqlite:///{tmp_path / 'constraints.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    user_id = uuid4()
    values = {
        "username": "alice",
        "display_name": "Alice",
        "password_hash": "test-only",
        "role": "customer",
    }
    try:
        with engine.begin() as connection:
            connection.execute(insert(User).values(id=user_id, **values))
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(insert(User).values(id=uuid4(), **values))
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                insert(User).values(
                    id=uuid4(), **{**values, "username": "bob", "role": "superadmin"}
                )
            )
        expires = datetime.now(UTC) + timedelta(hours=1)
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                insert(AuthSession).values(token_hash="a" * 64, user_id=uuid4(), expires_at=expires)
            )
        with engine.begin() as connection:
            connection.execute(
                insert(AuthSession).values(token_hash="b" * 64, user_id=user_id, expires_at=expires)
            )
            connection.execute(delete(User).where(User.id == user_id))
            assert connection.scalar(select(func.count()).select_from(AuthSession)) == 0
    finally:
        engine.dispose()
