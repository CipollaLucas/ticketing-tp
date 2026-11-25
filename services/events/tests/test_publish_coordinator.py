"""Recoverable multi-step publication, using real Events adapter and fake wire."""
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
    SqlAlchemyPublicationUnitOfWork,
)
from events_service.publication import PublicationRejected
from events_service.publish_coordinator import publish_via_ticketing
from events_service.sales_port import (
    SaleGateRejected,
    SaleGateState,
    SaleGateUnavailable,
)

NOW = datetime.now(UTC)
OWNER = uuid4()


class Wire:
    def __init__(self, event_id):
        self.event_id = event_id
        self.current = SaleGateState(event_id, "closed", 0, 0)
        self.commands = {}
        self.attempts = []
        self.provisions = 0
        self.drop_first_ack = False

    def provision(self, event_id, request_id=None):
        assert event_id == self.event_id
        self.provisions += 1
        return self.current

    def command(self, value, request_id=None):
        self.attempts.append(value)
        if value.command_id in self.commands:
            historical_command, response = self.commands[value.command_id]
            assert historical_command == value
            return response
        if self.current.state != "closed" or self.current.version != value.expected_version:
            raise SaleGateRejected("Stale gate")
        assert value.event_revision > self.current.event_revision
        self.current = SaleGateState(
            self.event_id, "open", self.current.version + 1, value.event_revision,
        )
        self.commands[value.command_id] = (value, self.current)
        if self.drop_first_ack:
            self.drop_first_ack = False
            raise SaleGateUnavailable("Remote committed but HTTP ACK lost")
        return self.current


@pytest.fixture
def context():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = NOW + timedelta(days=4)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Published show",
            description="Full description", venue="Arena",
            start_at=start, end_at=start + timedelta(hours=2),
            status="draft", revision=0,
        ))
        db.commit()
    wire = Wire(event_id)
    try:
        yield engine, event_id, wire
    finally:
        engine.dispose()


def run(engine, event_id, wire, *, owner=OWNER, role="event_owner"):
    with Session(engine) as db:
        return publish_via_ticketing(
            SqlAlchemyPublicationUnitOfWork(db), wire, wire,
            event_id, owner, role, NOW, "trace",
        )


def test_publish_durably_changes_metadata_then_opens_once(context):
    engine, event_id, wire = context
    result = run(engine, event_id, wire)
    assert result.gate.state == "open"
    assert result.gate.version == 1 and result.gate.event_revision == 1
    with Session(engine) as db:
        event = db.get(EventRow, event_id)
        intent = db.get(PublicationIntentRow, event_id)
        assert event.status == "published" and event.revision == 1
        assert intent.phase == "metadata_published"
        assert intent.expected_gate_version == 0
        assert result.intent.command_id == intent.command_id
    assert wire.provisions == 1
    again = run(engine, event_id, wire)
    assert again.intent == result.intent
    assert again.gate == result.gate
    assert wire.provisions == 1
    assert len({c.command_id for c in wire.attempts}) == 1


def test_lost_remote_ack_replays_exact_same_command(context):
    engine, event_id, wire = context
    wire.drop_first_ack = True
    with pytest.raises(SaleGateUnavailable):
        run(engine, event_id, wire)
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
        saved = db.get(PublicationIntentRow, event_id)
        command_id = saved.command_id
        assert saved.phase == "metadata_published"
    completed = run(engine, event_id, wire)
    assert completed.intent.command_id == command_id
    assert completed.gate.state == "open"
    assert len(wire.commands) == 1
    assert len(wire.attempts) == 2
    assert wire.attempts[0] == wire.attempts[1]


def test_remote_conflict_never_forces_gate_open(context):
    engine, event_id, wire = context
    wire.current = SaleGateState(event_id, "open", 9, 8)
    with pytest.raises(PublicationRejected) as error:
        run(engine, event_id, wire)
    assert error.value.status == 409
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "draft"
    assert wire.attempts == []


def test_unauthorized_never_calls_remote(context):
    engine, event_id, wire = context
    with pytest.raises(PublicationRejected) as error:
        run(engine, event_id, wire, owner=uuid4())
    assert error.value.status == 403
    assert wire.provisions == 0
    assert wire.attempts == []


def test_stale_gate_snapshot_remote_rejects_without_unsafe_open(context):
    engine, event_id, wire = context
    with Session(engine) as db:
        from events_service.publication import (
            prepare_publication,
            record_closed_gate_snapshot,
        )
        unit = SqlAlchemyPublicationUnitOfWork(db)
        prepare_publication(unit, event_id, OWNER, "event_owner", NOW)
        record_closed_gate_snapshot(
            unit, event_id, OWNER, "event_owner",
            SaleGateState(event_id, "closed", 0, 0),
        )
    wire.current = SaleGateState(event_id, "closed", 2, 0)
    with pytest.raises(SaleGateRejected):
        run(engine, event_id, wire)
    assert wire.current.state == "closed"
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
        assert db.get(PublicationIntentRow, event_id).expected_gate_version == 0
