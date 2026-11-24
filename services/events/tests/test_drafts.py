"""Application use-case tests run without any database or HTTP service."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from events_service.drafts import DraftInput, create_draft

NOW = datetime(2026, 11, 24, tzinfo=UTC)


class FakeWriter:
    def __init__(self, fail=False):
        self.fail = fail
        self.rows = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, event):
        self.rows.append(event)
        if self.fail:
            raise RuntimeError("Injected database error")

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def draft(**kwargs):
    data = dict(
        name="  Festival  ", description="Live music", venue="  Hall  ",
        start_at=NOW + timedelta(days=3), end_at=NOW + timedelta(days=3, hours=2),
    )
    return DraftInput(**(data | kwargs))


def test_draft_is_owned_by_authenticated_principal_and_persisted_once():
    writer = FakeWriter()
    owner = uuid4()
    created = create_draft(draft(), owner, writer, NOW)
    assert created.owner_id == owner
    assert created.status == "draft"
    assert created.name == "Festival" and created.venue == "Hall"
    assert writer.rows == [created]
    assert writer.commits == 1 and writer.rollbacks == 0


@pytest.mark.parametrize("payload", [
    draft(start_at=NOW),
    draft(end_at=NOW + timedelta(days=1)),
    draft(start_at=datetime(2026, 11, 26), end_at=datetime(2026, 11, 27)),
    draft(name=" "),
    draft(name="x" * 201),
    draft(description="bad\x00value"),
])
def test_invalid_draft_never_mutates_repository(payload):
    writer = FakeWriter()
    with pytest.raises(ValueError):
        create_draft(payload, uuid4(), writer, NOW)
    assert writer.rows == [] and writer.commits == 0


def test_writer_failure_rolls_back():
    writer = FakeWriter(fail=True)
    with pytest.raises(RuntimeError, match="Injected"):
        create_draft(draft(), uuid4(), writer, NOW)
    assert writer.commits == 0 and writer.rollbacks == 1
