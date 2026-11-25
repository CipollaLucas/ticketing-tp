"""HTTP Stage I publish contract is disabled by default and recoverable."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.commands import identity_port, publication_ports, session_scope
from events_service.identity import IdentityUnauthorized, IdentityUnavailable, Principal
from events_service.main import app
from events_service.persistence import Base, EventRow, PublicationIntentRow
from events_service.sales_port import SaleGateState, SaleGateUnavailable
from events_service.settings import settings

OWNER = uuid4()


class IdentityStub:
    def __init__(self):
        self.user_id = OWNER
        self.role = "event_owner"
        self.failure = None

    def introspect(self, token, request_id=None):
        assert token == "owner-token"
        if self.failure:
            raise self.failure
        return Principal(self.user_id, "owner", self.role)


class Wire:
    def __init__(self, event_id):
        self.event_id = event_id
        self.state = SaleGateState(event_id, "closed", 0, 0)
        self.commands = {}
        self.lost_ack = False
        self.provision_calls = 0

    def provision(self, event_id, request_id=None):
        assert event_id == self.event_id
        self.provision_calls += 1
        return self.state

    def command(self, value, request_id=None):
        if value.command_id in self.commands:
            return self.commands[value.command_id]
        self.state = SaleGateState(
            value.event_id, "open", value.expected_version + 1, value.event_revision,
        )
        self.commands[value.command_id] = self.state
        if self.lost_ack:
            self.lost_ack = False
            raise SaleGateUnavailable("lost after commit")
        return self.state


@pytest.fixture
def isolated(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    start = datetime.now(UTC) + timedelta(days=5)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Festival", description="Music",
            venue="Arena", start_at=start, end_at=start + timedelta(hours=2),
            status="draft", revision=0,
        ))
        db.commit()

    def database():
        with Session(engine) as db:
            yield db

    identity = IdentityStub()
    wire = Wire(event_id)
    app.dependency_overrides[session_scope] = database
    app.dependency_overrides[identity_port] = lambda: identity
    app.dependency_overrides[publication_ports] = lambda: (wire, wire)
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)
    monkeypatch.setattr(settings, "publication_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, engine, identity, wire, event_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def url(event_id):
    return f"/api/v1/events/{event_id}/publish"


def headers():
    return {"Authorization": "Bearer owner-token", "X-Request-ID": "trace-1"}


def test_route_publishes_with_exact_stage_one_shape_and_idempotency(isolated):
    client, engine, _, wire, event_id = isolated
    first = client.post(url(event_id), headers=headers(), json={})
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert set(first.json()) == {
        "id", "owner_id", "name", "description", "venue",
        "start_at", "end_at", "status", "created_at", "updated_at",
    }
    assert first.json()["status"] == "published"
    second = client.post(url(event_id), headers=headers(), json={})
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert wire.provision_calls == 1
    assert len(wire.commands) == 1
    with Session(engine) as db:
        assert db.get(EventRow, event_id).revision == 1


def test_lost_open_ack_returns_503_then_retries_same_command(isolated):
    client, engine, _, wire, event_id = isolated
    wire.lost_ack = True
    first = client.post(url(event_id), headers=headers(), json={})
    assert first.status_code == 503
    with Session(engine) as db:
        row = db.get(EventRow, event_id)
        assert row.status == "published"
        command_id = db.get(PublicationIntentRow, event_id).command_id
    again = client.post(url(event_id), headers=headers(), json={})
    assert again.status_code == 200
    assert command_id in wire.commands
    assert len(wire.commands) == 1


def test_disabled_and_invalid_identity_fail_closed(isolated, monkeypatch):
    client, engine, identity, wire, event_id = isolated
    monkeypatch.setattr(settings, "publication_enabled", False)
    assert client.post(url(event_id), headers=headers(), json={}).status_code == 404
    monkeypatch.setattr(settings, "publication_enabled", True)
    assert client.post(url(event_id), json={}).status_code == 401
    identity.failure = IdentityUnavailable("down")
    assert client.post(url(event_id), headers=headers(), json={}).status_code == 503
    identity.failure = IdentityUnauthorized("revoked")
    assert client.post(url(event_id), headers=headers(), json={}).status_code == 401
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "draft"
    assert not wire.commands


def test_cross_owner_and_customer_rejected_without_gate_change(isolated):
    client, _, identity, wire, event_id = isolated
    identity.user_id = uuid4()
    assert client.post(url(event_id), headers=headers(), json={}).status_code == 403
    identity.user_id = OWNER
    identity.role = "customer"
    assert client.post(url(event_id), headers=headers(), json={}).status_code == 403
    assert not wire.commands


def test_extra_body_rejected_before_publication(isolated):
    client, _, _, wire, event_id = isolated
    assert client.post(
        url(event_id), headers=headers(), json={"open": True},
    ).status_code == 422
    assert not wire.commands
