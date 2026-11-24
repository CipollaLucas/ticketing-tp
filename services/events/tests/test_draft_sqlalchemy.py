"""Adapter owns the Events transaction only, not Identity or Legacy."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from events_service.drafts import DraftInput, create_draft
from events_service.persistence import Base, EventRow, SqlAlchemyDraftWriter


def test_draft_roundtrip_in_owned_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    owner = uuid4()
    with Session(engine) as db:
        created = create_draft(
            DraftInput("Concert", "Music", "Hall", now + timedelta(days=2),
                       now + timedelta(days=2, hours=2)),
            owner, SqlAlchemyDraftWriter(db), now,
        )
    with Session(engine) as db:
        row = db.scalar(select(EventRow).where(EventRow.id == created.id))
        assert row is not None
        assert row.owner_id == owner
        assert row.status == "draft"
        assert row.name == "Concert"
    engine.dispose()
