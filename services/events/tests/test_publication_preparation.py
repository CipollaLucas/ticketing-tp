"""Publication is prepared durably; it never opens Ticketing sales."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.domain import EventRecord
from events_service.edit_draft import EditEventError, EventPatch, edit_draft
from events_service.persistence import (
    Base,
    EventRow,
    PublicationIntentRow,
    SqlAlchemyDraftEditPort,
    SqlAlchemyPublicationUnitOfWork,
)
from events_service.publication import (
    PublicationRejected,
    prepare_publication,
    record_closed_gate_snapshot,
)
from events_service.sales_port import SaleGateState

NOW = datetime.now(UTC)
OWNER = uuid4()
EVENT = EventRecord(
    id=uuid4(), owner_id=OWNER, name="Concert", description="Description",
    venue="Hall", start_at=NOW + timedelta(days=4),
    end_at=NOW + timedelta(days=4, hours=2), status="draft",
)


class Stub:
    def __init__(self, event=EVENT):
        self.event = event
        self.intent = None
        self.revision = 0
        self.commits = 0
        self.rollbacks = 0

    def lock_event(self, event_id):
        return self.event if self.event and self.event.id == event_id else None

    def existing_intent(self, event_id):
        return self.intent

    def event_revision(self, event_id):
        return self.revision

    def persist_intent(self, intent):
        self.intent = intent

    def bind_gate_version(self, event_id, version):
        self.intent = replace(self.intent, expected_gate_version=version)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_preparation_preserves_draft_and_reuses_command_id():
    stub = Stub()
    first = prepare_publication(stub, EVENT.id, OWNER, "event_owner", NOW)
    second = prepare_publication(stub, EVENT.id, OWNER, "event_owner", NOW)
    assert first == second
    assert first.event_revision == 1
    assert first.phase == "prepared"
    assert stub.event.status == "draft"
    assert stub.commits == 2


@pytest.mark.parametrize("event,owner,role,status", [
    (None, OWNER, "event_owner", 404),
    (EVENT, uuid4(), "event_owner", 403),
    (EVENT, OWNER, "customer", 403),
    (replace(EVENT, status="published"), OWNER, "event_owner", 409),
    (replace(EVENT, description=""), OWNER, "event_owner", 422),
    (replace(EVENT, start_at=NOW - timedelta(days=1)), OWNER, "event_owner", 422),
])
def test_invalid_candidate_never_persists(event, owner, role, status):
    stub = Stub(event)
    with pytest.raises(PublicationRejected) as error:
        prepare_publication(stub, EVENT.id, owner, role, NOW)
    assert error.value.status == status
    assert stub.intent is None
    assert stub.rollbacks == 1


def test_administrator_allowed_and_revision_is_monotonic():
    stub = Stub()
    stub.revision = 8
    intent = prepare_publication(stub, EVENT.id, uuid4(), "administrator", NOW)
    assert intent.event_revision == 9


def test_sqlite_transaction_survives_retry_in_new_session_without_publication():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = NOW + timedelta(days=3)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Owned",
            description="Description", venue="Hall", start_at=start,
            end_at=start + timedelta(hours=2), status="draft",
            revision=0,
        ))
        db.commit()

    with Session(engine) as db:
        first = prepare_publication(
            SqlAlchemyPublicationUnitOfWork(db), event_id,
            OWNER, "event_owner", NOW,
        )
    with Session(engine) as db:
        second = prepare_publication(
            SqlAlchemyPublicationUnitOfWork(db), event_id,
            OWNER, "event_owner", NOW,
        )
        assert first == second
        assert db.get(PublicationIntentRow, event_id).command_id == first.command_id
        row = db.get(EventRow, event_id)
        assert row is not None
        assert row.status == "draft" and row.revision == 0
    engine.dispose()


def test_pending_publication_blocks_draft_edit_in_same_database():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = NOW + timedelta(days=6)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Unchanged",
            description="Description", venue="Hall", start_at=start,
            end_at=start + timedelta(hours=2), status="draft", revision=0,
        ))
        db.commit()
    with Session(engine) as db:
        prepare_publication(
            SqlAlchemyPublicationUnitOfWork(db), event_id, OWNER, "event_owner", NOW,
        )
    with Session(engine) as db:
        with pytest.raises(EditEventError) as error:
            edit_draft(
                event_id, OWNER, "event_owner",
                EventPatch({"name": "Must not change"}),
                SqlAlchemyDraftEditPort(db), NOW,
            )
        assert error.value.status == 409
    with Session(engine) as db:
        assert db.get(EventRow, event_id).name == "Unchanged"
        assert db.get(PublicationIntentRow, event_id) is not None
    engine.dispose()


def test_gate_snapshot_records_version_and_replay_preserves_original_command():
    unit = Stub()
    prepared = prepare_publication(unit, EVENT.id, OWNER, "event_owner", NOW)
    snapshot = SaleGateState(EVENT.id, "closed", 7, 0)
    captured = record_closed_gate_snapshot(
        unit, EVENT.id, OWNER, "event_owner", snapshot,
    )
    repeated = record_closed_gate_snapshot(
        unit, EVENT.id, OWNER, "event_owner", snapshot,
    )
    assert captured == repeated
    assert captured.command_id == prepared.command_id
    assert captured.event_revision == 1
    assert captured.expected_gate_version == 7
    assert unit.event.status == "draft"


@pytest.mark.parametrize("gate", [
    SaleGateState(EVENT.id, "open", 2, 0),
    SaleGateState(uuid4(), "closed", 2, 0),
    SaleGateState(EVENT.id, "closed", -1, 0),
    SaleGateState(EVENT.id, "closed", 2, 1),
])
def test_inconsistent_or_open_gate_snapshot_is_rejected(gate):
    unit = Stub()
    prepare_publication(unit, EVENT.id, OWNER, "event_owner", NOW)
    with pytest.raises(PublicationRejected) as error:
        record_closed_gate_snapshot(unit, EVENT.id, OWNER, "event_owner", gate)
    assert error.value.status == 409
    assert unit.intent.expected_gate_version is None


def test_gate_version_change_requires_reconciliation_not_rebinding():
    unit = Stub()
    prepare_publication(unit, EVENT.id, OWNER, "event_owner", NOW)
    record_closed_gate_snapshot(
        unit, EVENT.id, OWNER, "event_owner",
        SaleGateState(EVENT.id, "closed", 3, 0),
    )
    with pytest.raises(PublicationRejected) as error:
        record_closed_gate_snapshot(
            unit, EVENT.id, OWNER, "event_owner",
            SaleGateState(EVENT.id, "closed", 4, 0),
        )
    assert error.value.status == 409
    assert unit.intent.expected_gate_version == 3


def test_gate_snapshot_authorization_and_missing_preparation():
    unit = Stub()
    gate = SaleGateState(EVENT.id, "closed", 0, 0)
    with pytest.raises(PublicationRejected):
        record_closed_gate_snapshot(unit, EVENT.id, OWNER, "event_owner", gate)
    prepare_publication(unit, EVENT.id, OWNER, "event_owner", NOW)
    with pytest.raises(PublicationRejected) as error:
        record_closed_gate_snapshot(unit, EVENT.id, uuid4(), "event_owner", gate)
    assert error.value.status == 403
    assert unit.intent.expected_gate_version is None


def test_gate_snapshot_survives_new_database_session():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = NOW + timedelta(days=3)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Show", description="Details",
            venue="Hall", start_at=start, end_at=start + timedelta(hours=2),
            status="draft", revision=0,
        ))
        db.commit()
    with Session(engine) as db:
        prepared = prepare_publication(
            SqlAlchemyPublicationUnitOfWork(db), event_id, OWNER, "event_owner", NOW,
        )
    with Session(engine) as db:
        captured = record_closed_gate_snapshot(
            SqlAlchemyPublicationUnitOfWork(db), event_id, OWNER, "event_owner",
            SaleGateState(event_id, "closed", 4, 0),
        )
        assert captured.command_id == prepared.command_id
    with Session(engine) as db:
        replay = record_closed_gate_snapshot(
            SqlAlchemyPublicationUnitOfWork(db), event_id, OWNER, "event_owner",
            SaleGateState(event_id, "closed", 4, 0),
        )
        assert replay == captured
        assert db.get(PublicationIntentRow, event_id).expected_gate_version == 4
        assert db.get(EventRow, event_id).status == "draft"
    engine.dispose()
