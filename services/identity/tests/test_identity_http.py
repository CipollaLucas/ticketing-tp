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


# Golden HTTP behavior from docs/API-ETAPA-I.md and backend/app/auth.py.
# These tests preserve React's existing /api/v1 contract during Identity cutover.


def test_legacy_public_identity_contract_has_exact_user_and_token_shapes(client):
    http, _ = client
    created = http.post("/api/v1/auth/register", json={
        "username": "  PaRiTy_User  ",
        "display_name": "  Parity Demo  ",
        "password": "valid-test-password-2026",
    })
    assert created.status_code == 201, created.text
    assert set(created.json()) == {"id", "username", "display_name", "role"}
    assert created.json()["username"] == "parity_user"
    assert created.json()["display_name"] == "Parity Demo"
    assert created.json()["role"] == "customer"
    assert login(http, "parity_user").status_code == 200
    authenticated = login(http, "parity_user")
    assert set(authenticated.json()) == {"access_token", "token_type", "expires_in"}
    assert authenticated.json()["token_type"] == "bearer"
    assert authenticated.json()["expires_in"] == settings.session_ttl_seconds
    assert authenticated.headers["cache-control"] == "no-store"
    token = authenticated.json()["access_token"]
    profile = http.get("/api/v1/auth/me", headers=bearer(token))
    assert profile.status_code == 200
    assert profile.json() == created.json()
    assert http.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 204
    assert http.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401
    assert http.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("payload", [
    {
        "username": "xy", "display_name": "Valid",
        "password": "valid-test-password-2026",
    },
    {
        "username": "valid_user", "display_name": "",
        "password": "valid-test-password-2026",
    },
    {
        "username": "valid_user", "display_name": "Valid",
        "password": "too-short",
    },
    {
        "username": "valid_user", "display_name": "Valid",
        "password": "valid-test-password-2026", "role": "administrator",
    },
    {
        "username": "valid_user", "display_name": "Valid",
        "password": "valid-test-password-2026", "id": "injected",
    },
])
def test_legacy_registration_rejects_invalid_or_injected_fields(client, payload):
    http, _ = client
    response = http.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert "valid-test-password-2026" not in response.text


def test_legacy_auth_failure_and_profile_authorization_contract(client):
    http, _ = client
    first = register(http, "first_customer").json()
    second = register(http, "second_customer").json()
    first_token = login(http, "first_customer").json()["access_token"]
    assert http.post("/api/v1/auth/login", json={
        "username": "first_customer", "password": "invalid-password-2026",
    }).status_code == 401
    no_auth = http.get("/api/v1/auth/me")
    assert no_auth.status_code == 401
    assert no_auth.headers["www-authenticate"] == "Bearer"
    other_profile = http.patch(
        f"/api/v1/users/{second['id']}", headers=bearer(first_token),
        json={"display_name": "Not allowed"},
    )
    assert other_profile.status_code == 403
    assert http.patch(
        f"/api/v1/users/{first['id']}", headers=bearer(first_token),
        json={"display_name": "New Name", "role": "administrator"},
    ).status_code == 422
    changed = http.patch(
        f"/api/v1/users/{first['id']}", headers=bearer(first_token),
        json={"display_name": "  New Name  "},
    )
    assert changed.status_code == 200
    assert changed.json()["display_name"] == "New Name"
    assert changed.json()["role"] == "customer"


def test_role_update_is_live_for_preexisting_session(client):
    http, engine = client
    owner = register(http, "promoted_owner").json()
    token = login(http, "promoted_owner").json()["access_token"]
    from identity.adapters.http import passwords
    with Session(engine) as db:
        db.add(UserRow(
            username="parity_admin", display_name="Admin",
            password_hash=passwords.hash("valid-test-password-2026"),
            role=Role.ADMINISTRATOR.value,
        ))
        db.commit()
    admin_token = login(http, "parity_admin").json()["access_token"]
    route = f"/api/v1/admin/users/{owner['id']}/role"
    assert http.patch(route, headers=bearer(token), json={
        "role": "event_owner",
    }).status_code == 403
    promoted = http.patch(route, headers=bearer(admin_token), json={
        "role": "event_owner",
    })
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "event_owner"
    assert http.get("/api/v1/auth/me", headers=bearer(token)).json()["role"] == "event_owner"
    demoted = http.patch(route, headers=bearer(admin_token), json={
        "role": "customer",
    })
    assert demoted.status_code == 200
    assert http.get("/api/v1/auth/me", headers=bearer(token)).json()["role"] == "customer"
