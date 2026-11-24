"""Canary cannot authorize work; fails closed on revocation, drift or outage."""
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.identity_canary import identity_adapter, router
from app.models import User
from app.settings import settings
from app.ticketing_core.application.identity import (
    AuthenticatedPrincipal,
    IdentityUnauthorized,
    IdentityUnavailable,
)

ID = UUID("00000000-0000-0000-0000-000000000019")


class FakeIdentity:
    def __init__(self, error=None, role="customer", username="canary_user"):
        self.error = error
        self.principal = AuthenticatedPrincipal(ID, username, "Canary", role)

    def introspect(self, token, request_id=None):
        if self.error:
            raise self.error
        assert token == "identity-only-token"
        return self.principal


@pytest.fixture
def context(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(
            id=ID, username="canary_user", display_name="Canary",
            role="customer", password_hash="hash",
        ))
        db.commit()

    app = FastAPI()
    app.include_router(router)

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    monkeypatch.setattr(settings, "identity_canary_enabled", True)
    app.dependency_overrides[identity_adapter] = lambda: FakeIdentity()
    with TestClient(app) as client:
        yield client, app, engine
    app.dependency_overrides.clear()
    engine.dispose()


def test_disabled_canary_is_not_accessible(context, monkeypatch):
    client, _, _ = context
    monkeypatch.setattr(settings, "identity_canary_enabled", False)
    response = client.get(
        "/api/v1/identity/canary",
        headers={"Authorization": "Bearer identity-only-token"},
    )
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


def test_valid_identity_and_legacy_uuid_role_match(context):
    client, _, _ = context
    response = client.get(
        "/api/v1/identity/canary",
        headers={"Authorization": "Bearer identity-only-token"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(ID)
    assert response.json()["identity_verified"] is True
    assert response.json()["legacy_uuid_role_match"] is True
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("error,status", [
    (IdentityUnauthorized("revoked"), 401),
    (IdentityUnavailable("timeout"), 503),
])
def test_remote_rejection_denies_canary(context, error, status):
    client, app, _ = context
    app.dependency_overrides[identity_adapter] = lambda: FakeIdentity(error=error)
    response = client.get(
        "/api/v1/identity/canary",
        headers={"Authorization": "Bearer identity-only-token"},
    )
    assert response.status_code == status
    assert "identity-only-token" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


def test_missing_bearer_does_not_fall_back_to_legacy(context):
    client, _, _ = context
    response = client.get("/api/v1/identity/canary")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("role,username", [
    ("administrator", "canary_user"), ("customer", "not_same_user"),
])
def test_mismatched_identity_is_rejected(context, role, username):
    client, app, _ = context
    app.dependency_overrides[identity_adapter] = lambda: FakeIdentity(
        role=role, username=username,
    )
    response = client.get(
        "/api/v1/identity/canary",
        headers={"Authorization": "Bearer identity-only-token"},
    )
    assert response.status_code == 409
    assert "identity-only-token" not in response.text


def test_missing_legacy_uuid_is_rejected(context):
    client, app, engine = context
    with Session(engine) as db:
        row = db.get(User, ID)
        db.delete(row)
        db.commit()
    app.dependency_overrides[identity_adapter] = lambda: FakeIdentity()
    response = client.get(
        "/api/v1/identity/canary",
        headers={"Authorization": "Bearer identity-only-token"},
    )
    assert response.status_code == 409
