"""HTTP contract and independent persistence tests for Identity."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from identity.adapters.persistence import Base, UserRow
from identity.database import get_db
from identity.domain.model import Role
from identity.main import app
from identity.settings import settings


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enforce_fks(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, username, name="Demo"):
    return client.post("/api/v1/auth/register", json={
        "username": username, "display_name": name, "password": "valid-test-password-2026",
    })


def login(client, username):
    return client.post("/api/v1/auth/login", json={
        "username": username, "password": "valid-test-password-2026",
    })


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_registration_login_logout_revocation(client):
    http, _ = client
    created = register(http, "buyer_demo")
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "customer"
    assert "password_hash" not in created.json()
    assert register(http, "buyer_demo").status_code == 409
    assert login(http, "unknown").status_code == 401
    assert login(http, "buyer_demo").status_code == 200
    token_response = login(http, "buyer_demo")
    assert token_response.headers["cache-control"] == "no-store"
    token = token_response.json()["access_token"]
    assert http.get("/api/v1/auth/me", headers=bearer(token)).json()["id"] == created.json()["id"]
    assert http.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 204
    assert http.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_admin_role_change_and_profile_authorization(client):
    http, engine = client
    customer = register(http, "owner_candidate").json()
    other = register(http, "another_customer").json()
    with Session(engine) as db:
        admin = UserRow(
            username="admin_test", display_name="Admin",
            password_hash="bootstrap-only", role=Role.ADMINISTRATOR.value,
        )
        db.add(admin)
        db.commit()
        admin_id = admin.id

    # For this test, bootstrap a valid Argon2 password through the real adapter.
    from identity.adapters.http import passwords
    with Session(engine) as db:
        admin_row = db.get(UserRow, admin_id)
        admin_row.password_hash = passwords.hash("valid-test-password-2026")
        db.commit()

    admin_token = login(http, "admin_test").json()["access_token"]
    customer_token = login(http, "owner_candidate").json()["access_token"]
    route = f"/api/v1/admin/users/{customer['id']}/role"
    assert http.patch(route, headers=bearer(customer_token),
                      json={"role": "event_owner"}).status_code == 403
    assert http.patch(
        f"/api/v1/admin/users/{admin_id}", headers=bearer(admin_token),
        json={"role": "customer"},
    ).status_code == 404
    assert http.patch(
        f"/api/v1/admin/users/{admin_id}/role", headers=bearer(admin_token),
        json={"role": "customer"},
    ).status_code == 409
    changed = http.patch(route, headers=bearer(admin_token), json={"role": "event_owner"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "event_owner"
    assert http.get("/api/v1/auth/me", headers=bearer(customer_token)).json()["role"] == "event_owner"
    assert http.patch(f"/api/v1/users/{other['id']}", headers=bearer(customer_token),
                      json={"display_name": "Hijack"}).status_code == 403
    assert http.patch(f"/api/v1/users/{customer['id']}", headers=bearer(customer_token),
                      json={"display_name": "Updated"}).status_code == 200


def test_internal_introspection_requires_service_credential(client):
    http, _ = client
    register(http, "private_user")
    token = login(http, "private_user").json()["access_token"]
    endpoint = "/api/v1/internal/auth/introspect"
    assert http.get(endpoint, headers=bearer(token)).status_code in (403, 422)
    assert http.get(endpoint, headers={
        **bearer(token), "X-Internal-Service-Token": "wrong",
    }).status_code == 403
    response = http.get(endpoint, headers={
        **bearer(token),
        "X-Internal-Service-Token": settings.identity_internal_token,
    })
    assert response.status_code == 200
    assert response.json()["username"] == "private_user"
    assert "password_hash" not in response.json()
    assert http.get(endpoint, headers={
        **bearer("invalid"),
        "X-Internal-Service-Token": settings.identity_internal_token,
    }).status_code == 401


def test_expired_sessions_are_rejected(client):
    http, engine = client
    register(http, "expired_user")
    token = login(http, "expired_user").json()["access_token"]
    from identity.adapters.persistence import SessionRow
    with Session(engine) as db:
        sessions = db.query(SessionRow).all()
        assert len(sessions) == 1
        sessions[0].expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert http.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_validation_does_not_echo_password(client):
    http, _ = client
    password = "secret-that-must-not-leak"
    response = http.post("/api/v1/auth/register", json={
        "username": "ab", "password": password, "display_name": "",
    })
    assert response.status_code == 422
    assert password not in response.text
