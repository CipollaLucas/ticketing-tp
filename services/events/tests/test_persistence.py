"""SQLite adapter tests; CI separately verifies PostgreSQL and Alembic."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from events_service.application import public_catalog
from events_service.persistence import Base, EventRow, SqlAlchemyEventReader


def test_events_adapter_owns_read_model_without_external_fk():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    foreign_owner = uuid4()
    with Session(engine) as db:
        db.add_all([
            EventRow(
                id=uuid4(), owner_id=foreign_owner, name="Live", description="A",
                venue="Hall", start_at=now + timedelta(days=2),
                end_at=now + timedelta(days=3), status="published",
            ),
            EventRow(
                id=uuid4(), owner_id=foreign_owner, name="Draft", description="B",
                venue="Hall", start_at=now + timedelta(days=2),
                end_at=now + timedelta(days=3), status="draft",
            ),
        ])
        db.commit()
        rows, total = public_catalog(SqlAlchemyEventReader(db), now)
    assert total == 1
    assert rows[0].name == "Live"
    assert rows[0].owner_id == foreign_owner
    assert EventRow.__table__.foreign_keys == set()
    engine.dispose()
