"""Opt-in HTTP unpublish contract, authorization and remote failure recovery."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.commands import identity_port, session_scope, unpublish_gate_port
from events_service.identity import IdentityUnauthorized, IdentityUnavailable, Principal
from events_service.main import app
from events_service.persistence import Base, EventRow, PublicationIntentRow, UnpublishIntentRow
from events_service.sales_port import SaleGateRejected, SaleGateState, SaleGateUnavailable
from events_service.settings import settings

OWNER = uuid4()


class Identity:
    def __init__(self):
        self.id = OWNER
        self.role = "event_owner"
        self.error = None

    def introspect(self, token, request_id=None):
        assert token == "owner-token"
        if self.error:
            raise self.error
        return Principal(self.id, "owner", self.role)


class Ticketing:
    def __init__(self, event_id):
        self.gate = SaleGateState(event_id, "open", 1, 1)
        self.commands = {}
        self.sales = False
        self.drop = False

    def state(self, event_id, request_id=None):
        return self.gate

    def close_without_sales(self, command, request_id=None):
        if command.command_id in self.commands:
            return self.commands[command.command_id]
        if self.sales:
            raise SaleGateRejected("Cannot unpublish an event with sales")
        if self.gate.version != command.expected_version:
            raise SaleGateRejected("Stale gate")
        self.gate = SaleGateState(
            command.event_id, "closed", command.expected_version + 1,
            command.event_revision,
        )
        self.commands[command.command_id] = self.gate
        if self.drop:
            self.drop = False
            raise SaleGateUnavailable("ACK lost")
        return self.gate


@pytest.fixture
def scenario(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = datetime.now(UTC) + timedelta(days=8)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Festival", description="Details",
            venue="Arena", start_at=start, end_at=start + timedelta(hours=1),
            status="published", revision=1,
        ))
        db.add(PublicationIntentRow(
            event_id=event_id, command_id=uuid4(),
            event_revision=1, expected_gate_version=0,
            phase="metadata_published",
        ))
        db.commit()

    def database():
        with Session(engine) as db:
            yield db

    identity, gate = Identity(), Ticketing(event_id)
    app.dependency_overrides[session_scope] = database
    app.dependency_overrides[identity_port] = lambda: identity
    app.dependency_overrides[unpublish_gate_port] = lambda: gate
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)
    monkeypatch.setattr(settings, "unpublication_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, engine, event_id, identity, gate
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def path(event_id):
    return f"/api/v1/events/{event_id}/unpublish"


def headers():
    return {"Authorization": "Bearer owner-token"}


def test_unpublish_matches_legacy_and_replay(scenario):
    client, engine, event_id, _, gate = scenario
    first = client.post(path(event_id), headers=headers(), json={})
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["status"] == "draft"
    assert len(first.json()) == 10
    replay = client.post(path(event_id), headers=headers(), json={})
    assert replay.status_code == 200 and replay.json() == first.json()
    assert len(gate.commands) == 1
    with Session(engine) as db:
        assert db.get(UnpublishIntentRow, event_id).phase == "completed"


def test_remote_lost_ack_returns_503_then_recovers(scenario):
    client, engine, event_id, _, gate = scenario
    gate.drop = True
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 503
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 200
    assert len(gate.commands) == 1


def test_sales_conflict_keeps_published(scenario):
    client, engine, event_id, _, gate = scenario
    gate.sales = True
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 409
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
    assert gate.gate.state == "open"


def test_disabled_missing_auth_or_revocation_fail_closed(scenario, monkeypatch):
    client, engine, event_id, identity, gate = scenario
    monkeypatch.setattr(settings, "unpublication_enabled", False)
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 404
    monkeypatch.setattr(settings, "unpublication_enabled", True)
    assert client.post(path(event_id), json={}).status_code == 401
    identity.error = IdentityUnavailable("down")
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 503
    identity.error = IdentityUnauthorized("revoked")
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 401
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "published"
    assert not gate.commands


def test_cross_owner_extra_fields_and_customer_denied(scenario):
    client, _, event_id, identity, gate = scenario
    identity.id = uuid4()
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 403
    identity.id = OWNER
    identity.role = "customer"
    assert client.post(path(event_id), headers=headers(), json={}).status_code == 403
    identity.role = "event_owner"
    assert client.post(
        path(event_id), headers=headers(), json={"force": True},
    ).status_code == 422
    assert not gate.commands
