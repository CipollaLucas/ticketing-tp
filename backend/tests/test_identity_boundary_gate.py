"""Regression gate: the opt-in remote canary is NOT a business authorization source.

These tests deliberately use the real FastAPI router wiring with a disposable
SQLite database; neither Identity nor Legacy persistent volumes are touched.
"""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.identity_canary import identity_adapter
from app.main import app
from app.models import AuthSession, Event, Order, Role, User
from app.settings import settings
from app.ticketing_core.application.identity import (
    AuthenticatedPrincipal,
    IdentityUnauthorized,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000027")
IDENTITY_TOKEN = "only-remote-identity-token"
LEGACY_TOKEN = "only-legacy-auth-session-token"


class RemoteVerifier:
    def introspect(self, token, request_id=None):
        if token != IDENTITY_TOKEN:
            raise IdentityUnauthorized("Not an Identity session")
        return AuthenticatedPrincipal(
            USER_ID, "shared_user", "Shared User", Role.EVENT_OWNER.value,
        )


@pytest.fixture
def boundary(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(
            id=USER_ID, username="shared_user", display_name="Shared User",
            password_hash="unused", role=Role.EVENT_OWNER.value,
        ))
        session.add(AuthSession(
            token_hash=sha256(LEGACY_TOKEN.encode()).hexdigest(),
            user_id=USER_ID,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ))
        session.commit()

    def disposable_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = disposable_db
    app.dependency_overrides[identity_adapter] = lambda: RemoteVerifier()
    monkeypatch.setattr(settings, "identity_canary_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_remote_only_token_can_pass_canary_but_not_legacy_business_routes(boundary):
    client, engine = boundary
    headers = {"Authorization": f"Bearer {IDENTITY_TOKEN}"}
    canary = client.get("/api/v1/identity/canary", headers=headers)
    assert canary.status_code == 200
    assert canary.json()["identity_verified"] is True

    # No protected endpoint may accept a canary-only token.
    for path in ("/api/v1/auth/me", "/api/v1/owner/events", "/api/v1/me/tickets"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401, (path, response.text)

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        assert session.scalar(select(func.count()).select_from(Order)) == 0


def test_legacy_only_session_cannot_pass_remote_canary(boundary):
    client, _ = boundary
    headers = {"Authorization": f"Bearer {LEGACY_TOKEN}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    canary = client.get("/api/v1/identity/canary", headers=headers)
    assert canary.status_code == 401
    assert "Cache-Control" in canary.headers
    assert canary.headers["Cache-Control"] == "no-store"
