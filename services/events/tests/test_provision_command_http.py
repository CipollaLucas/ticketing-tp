"""Protected Events PUT with isolated DB and stubbed remote Ticketing."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.commands import (
    gate_provision_port,
    identity_port,
    session_scope,
)
from events_service.identity import IdentityUnauthorized, IdentityUnavailable, Principal
from events_service.main import app
from events_service.persistence import Base, EventRow
from events_service.sales_port import SaleGateState, SaleGateUnavailable
from events_service.settings import settings

OWNER = uuid4()


class IdentityStub:
    def __init__(self):
        self.id = OWNER
        self.role = "event_owner"
        self.failure = None

    def introspect(self, token, request_id=None):
        assert token == "user-token"
        if self.failure:
            raise self.failure
        return Principal(self.id, "owner", self.role)


class TicketingStub:
    def __init__(self):
        self.calls = []
        self.failure = None

    def provision(self, event_id, request_id=None):
        self.calls.append((event_id, request_id))
        if self.failure:
            raise self.failure
        return SaleGateState(event_id, "closed", 0, 0)


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    identity, ticketing = IdentityStub(), TicketingStub()
    event_id = uuid4()
    start = datetime.now(UTC) + timedelta(days=3)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Show",
            description="Example", venue="Hall", start_at=start,
            end_at=start + timedelta(hours=2), status="draft",
        ))
        db.commit()

    def isolated_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = isolated_session
    app.dependency_overrides[identity_port] = lambda: identity
    app.dependency_overrides[gate_provision_port] = lambda: ticketing
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)
    monkeypatch.setattr(settings, "gate_provisioning_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, engine, identity, ticketing, event_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def url(event_id):
    return f"/api/v1/owner/events/{event_id}/sale-gate-provision"


def headers():
    return {"Authorization": "Bearer user-token", "X-Request-ID": "trace-1"}


def test_authorized_provision_is_closed_and_event_unchanged(ctx):
    client, engine, _, ticketing, event_id = ctx
    res = client.put(url(event_id), headers=headers())
    assert res.status_code == 200, res.text
    assert res.headers["cache-control"] == "no-store"
    assert res.json()["state"] == "closed"
    assert ticketing.calls == [(event_id, "trace-1")]
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "draft"


def test_other_owner_or_customer_never_calls_ticketing(ctx):
    client, _, identity, ticketing, event_id = ctx
    identity.id = uuid4()
    assert client.put(url(event_id), headers=headers()).status_code == 404
    identity.id = OWNER
    identity.role = "customer"
    assert client.put(url(event_id), headers=headers()).status_code == 404
    assert not ticketing.calls


def test_unknown_event_is_not_forwarded(ctx):
    client, _, _, ticketing, _ = ctx
    assert client.put(url(uuid4()), headers=headers()).status_code == 404
    assert not ticketing.calls


@pytest.mark.parametrize("failure,status", [
    (IdentityUnauthorized("revoked"), 401),
    (IdentityUnavailable("down"), 503),
])
def test_identity_failure_does_not_contact_ticketing(ctx, failure, status):
    client, _, identity, ticketing, event_id = ctx
    identity.failure = failure
    assert client.put(url(event_id), headers=headers()).status_code == status
    assert not ticketing.calls


def test_remote_timeout_is_503_and_event_remains_draft(ctx):
    client, engine, _, ticketing, event_id = ctx
    ticketing.failure = SaleGateUnavailable("uncertain")
    res = client.put(url(event_id), headers=headers())
    assert res.status_code == 503
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "draft"


def test_feature_off_and_missing_bearer(ctx, monkeypatch):
    client, _, _, ticketing, event_id = ctx
    assert client.put(url(event_id)).status_code == 401
    monkeypatch.setattr(settings, "gate_provisioning_enabled", False)
    assert client.put(url(event_id), headers=headers()).status_code == 404
    assert not ticketing.calls
