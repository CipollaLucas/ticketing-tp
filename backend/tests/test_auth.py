from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import AuthSession, Role, User

PASSWORD = "safe-test-passphrase-2026"


def register(client, username="alice", **extra):
    return client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": PASSWORD,
            "display_name": "Alice",
            **extra,
        },
    )


def login(client, username="alice"):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def account(client, db, username="alice", role=Role.CUSTOMER):
    response = register(client, username)
    assert response.status_code == 201, response.text
    user = db.get(User, UUID(response.json()["id"]))
    user.role = role.value
    db.commit()
    return user, headers(login(client, username))


def test_registration_normalizes_and_hashes_password(client, db):
    response = register(client, "  Alice_1  ", display_name="  Alice  ")
    assert response.status_code == 201
    data = response.json()
    assert data == {
        "id": data["id"],
        "username": "alice_1",
        "display_name": "Alice",
        "role": "customer",
    }
    user = db.get(User, UUID(data["id"]))
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert PASSWORD not in response.text


def test_normalized_duplicate_does_not_mutate_account(client, db):
    first = register(client)
    assert first.status_code == 201
    response = register(client, "ALICE", display_name="Changed")
    assert response.status_code == 409
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert db.scalar(select(User)).display_name == "Alice"


@pytest.mark.parametrize(
    "extra",
    [
        {"role": "administrator"},
        {"role": "event_owner"},
        {"id": str(uuid4())},
        {"password_hash": "fake"},
    ],
)
def test_registration_rejects_privilege_fields_without_creating_user(client, db, extra):
    assert register(client, **extra).status_code == 422
    assert db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab"},
        {"username": "a" * 51},
        {"username": "not valid"},
        {"username": "álice"},
        {"password": "bad-P@ss7"},
        {"password": "x" * 129},
        {"display_name": "  "},
        {"display_name": "x" * 101},
    ],
)
def test_registration_validates_inputs_and_does_not_echo_password(client, payload):
    response = register(client, **payload)
    assert response.status_code == 422
    assert payload.get("password", PASSWORD) not in response.text


def test_login_persists_only_token_digest_and_logout_revokes(client, db):
    account(client, db)
    token = login(client, " ALICE ")
    digest = sha256(token.encode()).hexdigest()
    session = db.get(AuthSession, digest)
    assert session is not None
    assert session.token_hash != token
    response = client.get("/api/v1/auth/me", headers=headers(token))
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert "password_hash" not in response.text
    assert token not in response.text
    assert client.post("/api/v1/auth/logout", headers=headers(token)).status_code == 204
    assert db.get(AuthSession, digest) is None
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=headers(token)).status_code == 401


def test_login_returns_unique_tokens_and_configured_lifetime(client, db):
    register(client)
    first = client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    second = login(client)
    assert first.status_code == 200
    assert first.json()["token_type"] == "bearer"
    assert first.json()["expires_in"] == 3600
    assert first.json()["access_token"] != second
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 2


@pytest.mark.parametrize("username", ["alice", "unknown"])
def test_invalid_login_is_generic_and_creates_no_session(client, db, username):
    register(client)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": "incorrect-password",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0


@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer", "Bearer unknown"])
def test_missing_malformed_or_unknown_credentials(client, authorization):
    auth = {} if authorization is None else {"Authorization": authorization}
    response = client.get("/api/v1/auth/me", headers=auth)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_session_is_unauthorized(client, db):
    _, auth = account(client, db)
    session = db.scalar(select(AuthSession))
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401


def test_logout_revokes_only_current_session(client, db):
    _, auth = account(client, db)
    other_token = login(client)
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers(other_token)).status_code == 200


def test_profile_update_requires_owner_or_admin_and_does_not_mutate_foreign_user(client, db):
    alice, alice_auth = account(client, db, "alice", Role.EVENT_OWNER)
    bob, bob_auth = account(client, db, "bob", Role.EVENT_OWNER)
    response = client.patch(
        f"/api/v1/users/{alice.id}", headers=bob_auth, json={"display_name": "Stolen"}
    )
    assert response.status_code == 403
    db.refresh(alice)
    assert alice.display_name == "Alice"
    response = client.patch(
        f"/api/v1/users/{alice.id}", headers=alice_auth, json={"display_name": " Updated "}
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated"
    _, admin_auth = account(client, db, "admin", Role.ADMINISTRATOR)
    assert (
        client.patch(
            f"/api/v1/users/{bob.id}", headers=admin_auth, json={"display_name": "Admin edit"}
        ).status_code
        == 200
    )


@pytest.mark.parametrize("role", [Role.CUSTOMER, Role.EVENT_OWNER])
def test_only_admin_changes_roles_and_denial_does_not_mutate(client, db, role):
    user, auth = account(client, db, role=role)
    response = client.patch(
        f"/api/v1/admin/users/{user.id}/role", headers=auth, json={"role": "administrator"}
    )
    assert response.status_code == 403
    db.refresh(user)
    assert user.role == role.value
    assert (
        client.patch(
            f"/api/v1/users/{user.id}", headers=auth, json={"role": "administrator"}
        ).status_code
        == 422
    )


def test_admin_changes_role_and_existing_session_observes_revocation(client, db):
    owner, owner_auth = account(client, db, "owner", Role.ADMINISTRATOR)
    admin, admin_auth = account(client, db, "admin", Role.ADMINISTRATOR)
    response = client.patch(
        f"/api/v1/admin/users/{owner.id}/role", headers=admin_auth, json={"role": "customer"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "customer"
    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/role", headers=owner_auth, json={"role": "customer"}
    )
    assert response.status_code == 403
    db.refresh(admin)
    assert admin.role == "administrator"


def test_admin_cannot_change_own_role(client, db):
    user, auth = account(client, db, role=Role.ADMINISTRATOR)
    assert (
        client.patch(
            f"/api/v1/admin/users/{user.id}/role", headers=auth, json={"role": "customer"}
        ).status_code
        == 409
    )
    db.refresh(user)
    assert user.role == "administrator"


def test_missing_user_and_invalid_role(client, db):
    _, auth = account(client, db, role=Role.ADMINISTRATOR)
    missing = uuid4()
    assert (
        client.patch(
            f"/api/v1/users/{missing}", headers=auth, json={"display_name": "Nobody"}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/admin/users/{missing}/role", headers=auth, json={"role": "customer"}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/admin/users/{missing}/role", headers=auth, json={"role": "superadmin"}
        ).status_code
        == 422
    )


def test_swagger_describes_bearer_and_never_exposes_hashes():
    from app.main import app

    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    properties = schema["components"]["schemas"]["UserResponse"]["properties"]
    assert "password_hash" not in properties
    assert "password" not in properties


@pytest.mark.parametrize(
    "role,foreign,status",
    [
        (Role.CUSTOMER, False, 403),
        (Role.EVENT_OWNER, True, 403),
        (Role.EVENT_OWNER, False, 200),
        (Role.ADMINISTRATOR, True, 200),
    ],
)
def test_event_edit_guards_reject_before_mutation(client, db, role, foreign, status):
    from typing import Annotated

    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.auth import require_event_owner, require_owner_or_admin
    from app.database import get_db

    user, auth = account(client, db, role=role)
    resource = {"owner_id": uuid4() if foreign else user.id, "name": "Original"}
    # Test-only event route exercises the production guards; no event CRUD ships here.
    test_app = FastAPI()
    test_app.dependency_overrides[get_db] = lambda: db

    @test_app.patch("/events/demo")
    def edit_event(current: Annotated[User, Depends(require_event_owner)]):
        require_owner_or_admin(current, resource["owner_id"])
        resource["name"] = "Changed"
        return {"name": resource["name"]}

    with TestClient(test_app) as test_client:
        response = test_client.patch("/events/demo", headers=auth)
    assert response.status_code == status
    assert resource["name"] == ("Changed" if status == 200 else "Original")


def test_role_update_rechecks_administrator_after_authorization(client, db):
    from fastapi import HTTPException
    from sqlalchemy import update

    from app.auth import RoleUpdate, update_role

    actor, _ = account(client, db, "actor", Role.ADMINISTRATOR)
    target, _ = account(client, db, "target", Role.ADMINISTRATOR)
    # Simulate a second transaction revoking the actor after its auth dependency ran.
    db.execute(update(User).where(User.id == actor.id).values(role="customer"))
    db.commit()
    with pytest.raises(HTTPException) as error:
        update_role(target.id, RoleUpdate(role=Role.CUSTOMER), actor, db)
    assert error.value.status_code == 403
    db.refresh(target)
    assert target.role == "administrator"
