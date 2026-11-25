"""Events unpublish application: safe ordering, replays and lost close ACK."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.persistence import (
    Base,
    EventRow,
    PublicationIntentRow,
    SqlAlchemyUnpublishUnit,
    UnpublishIntentRow,
)
from events_service.sales_port import SaleGateRejected, SaleGateState, SaleGateUnavailable
from events_service.unpublish import UnpublishRejected, unpublish_via_ticketing

NOW = datetime.now(UTC)
OWNER = uuid4()


class Ticketing:
    def __init__(self, event_id):
        self.event_id = event_id
        self.gate = SaleGateState(event_id, "open", 1, 1)
        self.commands = {}
        self.calls = 0
        self.drop_ack = False
        self.has_sales = False

    def state(self, event_id, request_id=None):
        return self.gate

    def close_without_sales(self, command, request_id=None):
        self.calls += 1
        if command.command_id in self.commands:
            previous, result = self.commands[command.command_id]
            assert previous == command
            return result
        if self.has_sales:
            raise SaleGateRejected("Cannot unpublish an event with sales")
        if self.gate.version != command.expected_version or self.gate.state != "open":
            raise SaleGateRejected("Stale gate")
        self.gate = SaleGateState(
            self.event_id, "closed", self.gate.version + 1,
            command.event_revision,
        )
        self.commands[command.command_id] = (command, self.gate)
        if self.drop_ack:
            self.drop_ack = False
            raise SaleGateUnavailable("Committed but ack lost")
        return self.gate


@pytest.fixture
def context():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = NOW + timedelta(days=7)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Show",
            description="Description", venue="Arena",
            start_at=start, end_at=start + timedelta(hours=2),
            status="published", revision=1,
        ))
        db.add(PublicationIntentRow(
            event_id=event_id, command_id=uuid4(),
            event_revision=1, expected_gate_version=0,
            phase="metadata_published",
        ))
        db.commit()
    wire = Ticketing(event_id)
    try:
        yield engine, event_id, wire
    finally:
        engine.dispose()


def execute(engine, event_id, wire, owner=OWNER, role="event_owner"):
    with Session(engine) as db:
        return unpublish_via_ticketing(
            SqlAlchemyUnpublishUnit(db), wire, event_id, owner, role, NOW,
        )


def test_close_before_draft_and_repeat_is_stable(context):
    engine, event_id, wire = context
    first = execute(engine, event_id, wire)
    assert first.phase == "completed"
    assert wire.gate.state == "closed"
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "draft"
        assert db.get(EventRow, event_id).revision == 2
        assert db.get(PublicationIntentRow, event_id) is None
        assert db.get(UnpublishIntentRow, event_id).phase == "completed"
    again = execute(engine, event_id, wire)
    assert again == first
    assert wire.calls == 1


def test_lost_close_ack_keeps_published_until_replay(context):
    engine, event_id, wire = context
    wire.drop_ack = True
    with pytest.raises(SaleGateUnavailable):
        execute(engine, event_id, wire)
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
        saved_id = db.get(UnpublishIntentRow, event_id).command_id
    finished = execute(engine, event_id, wire)
    assert finished.command_id == saved_id
    assert finished.phase == "completed"
    assert len(wire.commands) == 1 and wire.calls == 2
    assert wire.gate.state == "closed"


def test_sales_prevent_draft_transition(context):
    engine, event_id, wire = context
    wire.has_sales = True
    with pytest.raises(SaleGateRejected):
        execute(engine, event_id, wire)
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
        assert db.get(UnpublishIntentRow, event_id).phase == "prepared"
    assert wire.gate.state == "open"


def test_wrong_actor_cannot_close(context):
    engine, event_id, wire = context
    with pytest.raises(UnpublishRejected) as error:
        execute(engine, event_id, wire, owner=uuid4())
    assert error.value.status == 403
    assert wire.calls == 0


def test_replay_after_close_with_different_actor_is_denied(context):
    engine, event_id, wire = context
    execute(engine, event_id, wire)
    with pytest.raises(UnpublishRejected) as error:
        execute(engine, event_id, wire, owner=uuid4())
    assert error.value.status == 403
