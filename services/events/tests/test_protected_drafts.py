"""HTTP authorization proof using the real Events SQLite adapter in isolation."""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.commands import identity_port, session_scope
from events_service.identity import IdentityUnauthorized, IdentityUnavailable, Principal
from events_service.main import app
from events_service.persistence import Base, EventRow
from events_service.settings import settings

OWNER = uuid4()


class IdentityStub:
    def __init__(self, role="event_owner", failure=None):
        self.role = role
        self.failure = failure
        self.calls = 0

    def introspect(self, token, request_id=None):
        self.calls += 1
        assert token == "remote-access-token"
        if self.failure:
            raise self.failure
        return Principal(OWNER, "organizer", self.role)


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    identity = IdentityStub()
    def isolated_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = isolated_session
    app.dependency_overrides[identity_port] = lambda: identity
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, engine, identity
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def payload():
    now = datetime.now(UTC) + timedelta(days=7)
    return {
        "name": "Festival", "description": "Music", "venue": "Hall",
        "start_at": now.isoformat(), "end_at": (now + timedelta(hours=2)).isoformat(),
    }


def count(engine):
    with Session(engine) as db:
        return db.scalar(select(func.count()).select_from(EventRow))


def test_protected_draft_creates_owned_record(ctx):
    client, engine, identity = ctx
    response = client.post(
        "/api/v1/events", headers={"Authorization": "Bearer remote-access-token"},
        json=payload(),
    )
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["owner_id"] == str(OWNER) and data["status"] == "draft"
    assert identity.calls == 1
    with Session(engine) as db:
        row = db.get(EventRow, UUID(data["id"]))
        assert row is not None and row.owner_id == OWNER


@pytest.mark.parametrize("role", ["customer"])
def test_role_denied_without_writes(ctx, role):
    client, engine, identity = ctx
    identity.role = role
    response = client.post(
        "/api/v1/events", headers={"Authorization": "Bearer remote-access-token"},
        json=payload(),
    )
    assert response.status_code == 403
    assert count(engine) == 0


@pytest.mark.parametrize("failure,status", [
    (IdentityUnauthorized("revoked"), 401),
    (IdentityUnavailable("offline"), 503),
])
def test_remote_rejection_never_writes(ctx, failure, status):
    client, engine, identity = ctx
    identity.failure = failure
    response = client.post(
        "/api/v1/events", headers={"Authorization": "Bearer remote-access-token"},
        json=payload(),
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert count(engine) == 0


def test_missing_token_and_owner_id_injection(ctx):
    client, engine, _ = ctx
    assert client.post("/api/v1/events", json=payload()).status_code == 401
    injected = payload() | {"owner_id": str(uuid4())}
    assert client.post(
        "/api/v1/events", headers={"Authorization": "Bearer remote-access-token"},
        json=injected,
    ).status_code == 422
    assert count(engine) == 0


def test_disabled_default_is_inaccessible_even_when_token_provided(ctx, monkeypatch):
    client, engine, _ = ctx
    monkeypatch.setattr(settings, "protected_drafts_enabled", False)
    response = client.post(
        "/api/v1/events", headers={"Authorization": "Bearer remote-access-token"},
        json=payload(),
    )
    assert response.status_code == 404
    assert count(engine) == 0


def test_invalid_future_date_never_writes(ctx):
    client, engine, _ = ctx
    data = payload()
    data["start_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v1/events", headers={"Authorization": "Bearer remote-access-token"},
        json=data,
    )
    assert response.status_code == 422
    assert count(engine) == 0


def test_owner_list_sees_own_drafts_only(ctx):
    client, engine, _ = ctx
    other_owner = uuid4()
    now = datetime.now(UTC) + timedelta(days=3)
    with Session(engine) as db:
        db.add(EventRow(
            id=uuid4(), owner_id=other_owner, name="Other person's draft",
            description="Private", venue="Hall", start_at=now,
            end_at=now + timedelta(hours=2), status="draft",
        ))
        db.commit()
    headers = {"Authorization": "Bearer remote-access-token"}
    create = client.post("/api/v1/events", headers=headers, json=payload())
    assert create.status_code == 201
    listing = client.get("/api/v1/owner/events", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.headers["cache-control"] == "no-store"
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["owner_id"] == str(OWNER)
    assert listing.json()["items"][0]["status"] == "draft"


def test_admin_listing_sees_all_events(ctx):
    client, engine, identity = ctx
    identity.role = "administrator"
    now = datetime.now(UTC) + timedelta(days=3)
    with Session(engine) as db:
        for owner_id in (OWNER, uuid4()):
            db.add(EventRow(
                id=uuid4(), owner_id=owner_id, name="Any draft",
                description="Private", venue="Hall", start_at=now,
                end_at=now + timedelta(hours=2), status="draft",
            ))
        db.commit()
    response = client.get(
        "/api/v1/owner/events",
        headers={"Authorization": "Bearer remote-access-token"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2


@pytest.mark.parametrize("failure,status", [
    (IdentityUnauthorized("revoked"), 401),
    (IdentityUnavailable("down"), 503),
])
def test_owner_listing_fails_closed(ctx, failure, status):
    client, _, identity = ctx
    identity.failure = failure
    response = client.get(
        "/api/v1/owner/events",
        headers={"Authorization": "Bearer remote-access-token"},
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"


def test_customer_cannot_list_private_events(ctx):
    client, _, identity = ctx
    identity.role = "customer"
    response = client.get(
        "/api/v1/owner/events",
        headers={"Authorization": "Bearer remote-access-token"},
    )
    assert response.status_code == 403


def test_owner_listing_preview_disabled(ctx, monkeypatch):
    client, _, _ = ctx
    monkeypatch.setattr(settings, "protected_drafts_enabled", False)
    response = client.get(
        "/api/v1/owner/events",
        headers={"Authorization": "Bearer remote-access-token"},
    )
    assert response.status_code == 404
