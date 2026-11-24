from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from events_service.application import public_catalog
from events_service.domain import EventRecord, is_publicly_visible, validate_event


NOW = datetime(2026, 11, 24, tzinfo=UTC)


def sample(status="published", start=None):
    start = start or NOW + timedelta(days=3)
    return EventRecord(
        id=uuid4(), owner_id=uuid4(), name="Concert", description="Preview",
        venue="Hall", start_at=start, end_at=start + timedelta(hours=2), status=status,
    )


def test_publication_rules_are_pure():
    assert is_publicly_visible(sample(), NOW)
    assert not is_publicly_visible(sample("draft"), NOW)
    assert not is_publicly_visible(sample(start=NOW - timedelta(days=1)), NOW)
    validate_event(sample())
    with pytest.raises(ValueError):
        validate_event(sample("wrong"))


def test_catalog_uses_port_without_orm():
    class FakeReader:
        def upcoming(self, now, limit, offset):
            assert (now, limit, offset) == (NOW, 20, 0)
            return [sample()], 1

    rows, total = public_catalog(FakeReader(), NOW)
    assert len(rows) == total == 1


def test_catalog_rejects_inconsistent_adapter():
    class UnsafeReader:
        def upcoming(self, now, limit, offset):
            return [sample("draft")], 1

    with pytest.raises(ValueError, match="non-public"):
        public_catalog(UnsafeReader(), NOW)


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (20, -1)])
def test_invalid_pagination(limit, offset):
    class NeverCalled:
        def upcoming(self, now, limit, offset):
            pytest.fail("Adapter must not be called")

    with pytest.raises(ValueError):
        public_catalog(NeverCalled(), NOW, limit, offset)
