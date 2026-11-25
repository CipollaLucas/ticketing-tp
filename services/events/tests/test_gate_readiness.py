"""Pure policy proves unknown/cross-owner/published/expired events are denied."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from events_service.domain import EventRecord
from events_service.gate_readiness import GateReadinessDenied, verify_gate_candidate

NOW = datetime.now(UTC)
OWNER = uuid4()
EVENT = EventRecord(
    id=uuid4(), owner_id=OWNER, name="Show", description="Example", venue="Hall",
    start_at=NOW + timedelta(days=2), end_at=NOW + timedelta(days=2, hours=2),
    status="draft",
)


class Reader:
    def __init__(self, event):
        self.event = event

    def by_id(self, event_id):
        return self.event if self.event and self.event.id == event_id else None


def test_event_owner_may_prepare_own_committed_upcoming_draft():
    verified = verify_gate_candidate(Reader(EVENT), EVENT.id, OWNER, "event_owner", NOW)
    assert verified.event_id == EVENT.id and verified.owner_id == OWNER


def test_administrator_may_verify_other_owner_event():
    verified = verify_gate_candidate(
        Reader(EVENT), EVENT.id, uuid4(), "administrator", NOW,
    )
    assert verified.status == "draft"


@pytest.mark.parametrize("row,actor,role", [
    (None, OWNER, "event_owner"),
    (EVENT, uuid4(), "event_owner"),
    (EVENT, OWNER, "customer"),
    (replace(EVENT, status="published"), OWNER, "event_owner"),
    (replace(EVENT, start_at=NOW - timedelta(days=1)), OWNER, "event_owner"),
])
def test_invalid_candidate_is_denied(row, actor, role):
    with pytest.raises(GateReadinessDenied):
        verify_gate_candidate(Reader(row), EVENT.id, actor, role, NOW)
