"""HTTP preflight enforces freshly verified Identity and committed Events ownership."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.commands import identity_port, session_scope
from events_service.identity import IdentityUnauthorized, IdentityUnavailable, Principal
from events_service.main import app
from events_service.persistence import Base, EventRow
from events_service.settings import settings

OWNER = uuid4()
OTHER = uuid4()


class Verifier:
    def __init__(self):
        self.role = "event_owner"
        self.id = OWNER
        self.failure = None

    def introspect(self, token, request_id=None):
        assert token == "valid-token"
        if self.failure:
            raise self.failure
        return Principal(self.id, "authorized-owner", self.role)


@pytest.fixture
def api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    verifier = Verifier()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = session
    app.dependency_overrides[identity_port] = lambda: verifier
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)
    event_id = uuid4()
    now = datetime.now(UTC)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Show",
            description="Example", venue="Hall",
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=2),
            status="draft",
        ))
        db.commit()
    try:
        with TestClient(app) as client:
            yield client, engine, verifier, event_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def url(event_id):
    return f"/api/v1/owner/events/{event_id}/sale-gate-readiness"


def headers():
    return {"Authorization": "Bearer valid-token"}


def test_authorized_owner_reads_committed_draft_without_mutating_it(api):
    client, engine, _, event_id = api
    res = client.get(url(event_id), headers=headers())
    assert res.status_code == 200, res.text
    assert res.headers["cache-control"] == "no-store"
    assert res.json()["ready_for_gate_provisioning"] is True
    assert res.json()["gate_provisioned"] is False
    with Session(engine) as db:
        assert db.get(EventRow, event_id).status == "draft"


def test_unknown_and_cross_owner_are_indistinguishable(api):
    client, _, verifier, event_id = api
    verifier.id = OTHER
    denied = client.get(url(event_id), headers=headers())
    missing = client.get(url(uuid4()), headers=headers())
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()


def test_admin_can_verify_draft(api):
    client, _, verifier, event_id = api
    verifier.role = "administrator"
    verifier.id = OTHER
    assert client.get(url(event_id), headers=headers()).status_code == 200


def test_customer_denied(api):
    client, _, verifier, event_id = api
    verifier.role = "customer"
    assert client.get(url(event_id), headers=headers()).status_code == 404


def test_published_event_denied(api):
    client, engine, _, event_id = api
    with Session(engine) as db:
        row = db.get(EventRow, event_id)
        row.status = "published"
        db.commit()
    assert client.get(url(event_id), headers=headers()).status_code == 404


@pytest.mark.parametrize("failure,expected", [
    (IdentityUnauthorized("revoked"), 401),
    (IdentityUnavailable("unreachable"), 503),
])
def test_rejected_or_unavailable_identity_fails_closed(api, failure, expected):
    client, _, verifier, event_id = api
    verifier.failure = failure
    assert client.get(url(event_id), headers=headers()).status_code == expected


def test_no_bearer_or_disabled_endpoint_denied(api, monkeypatch):
    client, _, _, event_id = api
    assert client.get(url(event_id)).status_code == 401
    monkeypatch.setattr(settings, "protected_drafts_enabled", False)
    assert client.get(url(event_id), headers=headers()).status_code == 404
