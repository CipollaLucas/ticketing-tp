"""Stage I draft PATCH uses Events-owned storage, rechecks Identity, rolls back."""
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


class IdentityStub:
    def __init__(self):
        self.id = OWNER
        self.role = "event_owner"
        self.error = None

    def introspect(self, token, request_id=None):
        assert token == "test-token"
        if self.error:
            raise self.error
        return Principal(self.id, "owner", self.role)


@pytest.fixture
def api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    identity = IdentityStub()
    now = datetime.now(UTC)
    event_id = uuid4()
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Original",
            description="Description", venue="Venue",
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=5, hours=2),
            status="draft", created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        ))
        db.commit()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = session
    app.dependency_overrides[identity_port] = lambda: identity
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, engine, identity, event_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def path(event_id):
    return f"/api/v1/events/{event_id}"


def headers():
    return {"Authorization": "Bearer test-token"}


def test_update_own_future_draft_preserves_creation_date(api):
    client, engine, _, event_id = api
    with Session(engine) as db:
        previous = db.get(EventRow, event_id).created_at
    response = client.patch(path(event_id), headers=headers(), json={"name": "  Updated  "})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Updated" and body["status"] == "draft"
    assert len(body) == 10 and body["created_at"] != body["updated_at"]
    with Session(engine) as db:
        persisted = db.get(EventRow, event_id)
        assert persisted.created_at == previous
        assert persisted.name == "Updated"


@pytest.mark.parametrize("changes", [
    {}, {"name": None}, {"name": ""}, {"status": "published"},
    {"owner_id": str(uuid4())}, {"name": "Bad\x00text"},
])
def test_invalid_patch_is_422_without_mutation(api, changes):
    client, engine, _, event_id = api
    response = client.patch(path(event_id), headers=headers(), json=changes)
    assert response.status_code == 422, response.text
    with Session(engine) as db:
        assert db.get(EventRow, event_id).name == "Original"


def test_cross_owner_and_customer_cannot_edit(api):
    client, engine, identity, event_id = api
    identity.id = uuid4()
    assert client.patch(path(event_id), headers=headers(), json={"name":"Other"}).status_code == 403
    identity.id = OWNER
    identity.role = "customer"
    assert client.patch(path(event_id), headers=headers(), json={"name":"Other"}).status_code == 403
    with Session(engine) as db:
        assert db.get(EventRow, event_id).name == "Original"


def test_published_event_rejects_mutation(api):
    client, engine, _, event_id = api
    with Session(engine) as db:
        db.get(EventRow, event_id).status = "published"
        db.commit()
    assert client.patch(path(event_id), headers=headers(), json={"name":"Other"}).status_code == 409


def test_invalid_dates_rollback(api):
    client, engine, _, event_id = api
    response = client.patch(path(event_id), headers=headers(), json={
        "start_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    })
    assert response.status_code == 422
    with Session(engine) as db:
        assert db.get(EventRow, event_id).name == "Original"


@pytest.mark.parametrize("error,status", [
    (IdentityUnauthorized("revoked"), 401),
    (IdentityUnavailable("down"), 503),
])
def test_identity_failure_prevents_mutation(api, error, status):
    client, engine, identity, event_id = api
    identity.error = error
    assert client.patch(path(event_id), headers=headers(), json={"name":"Other"}).status_code == status
    with Session(engine) as db:
        assert db.get(EventRow, event_id).name == "Original"


def test_absent_bearer_and_disabled_preview(api, monkeypatch):
    client, _, _, event_id = api
    assert client.patch(path(event_id), json={"name":"Other"}).status_code == 401
    monkeypatch.setattr(settings, "protected_drafts_enabled", False)
    assert client.patch(path(event_id), headers=headers(), json={"name":"Other"}).status_code == 404


def test_administrator_may_edit_other_owners_draft(api):
    client, _, identity, event_id = api
    identity.id = uuid4()
    identity.role = "administrator"
    assert client.patch(path(event_id), headers=headers(), json={"venue":"New Venue"}).status_code == 200
