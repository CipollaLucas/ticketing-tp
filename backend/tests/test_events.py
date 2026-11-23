"""Event draft and catalog contract tests."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select

from app.models import AuthSession, Event, EventStatus, Role, User


def signed_in(db, role: Role, username: str) -> dict[str, str]:
    user = User(username=username, display_name=username, password_hash="not-used", role=role.value)
    db.add(user)
    db.flush()
    token = f"token-for-{username}"
    db.add(
        AuthSession(
            token_hash=sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def dates() -> dict[str, str]:
    start = datetime.now(UTC) + timedelta(days=30)
    return {"start_at": start.isoformat(), "end_at": (start + timedelta(hours=3)).isoformat()}


def create(client, auth, **fields):
    return client.post("/api/v1/events", headers=auth, json={"name": "Demo", **fields})


def test_owner_creates_draft_and_can_edit(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    response = create(client, owner)
    assert response.status_code == 201, response.text
    event_id = response.json()["id"]
    assert response.json()["status"] == "draft"
    assert response.json()["owner_id"] == str(db.scalar(select(User.id)))
    changed = client.patch(
        f"/api/v1/events/{event_id}", headers=owner, json={"venue": "Auditorio", **dates()}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["venue"] == "Auditorio"
    assert db.scalar(select(func.count()).select_from(Event)) == 1


def test_customer_and_anonymous_cannot_create(client, db):
    customer = signed_in(db, Role.CUSTOMER, "customer")
    assert create(client, customer).status_code == 403
    assert client.post("/api/v1/events", json={"name": "Not allowed"}).status_code == 401
    assert db.scalar(select(func.count()).select_from(Event)) == 0


def test_foreign_owner_blocked_without_mutation(client, db):
    a = signed_in(db, Role.EVENT_OWNER, "owner_a")
    b = signed_in(db, Role.EVENT_OWNER, "owner_b")
    event_id = create(client, a).json()["id"]
    assert client.patch(
        f"/api/v1/events/{event_id}", headers=b, json={"name": "Hijacked"}
    ).status_code == 403
    assert client.post(f"/api/v1/events/{event_id}/publish", headers=b).status_code == 403
    assert db.get(Event, UUID(event_id)).name == "Demo"


def test_admin_can_edit_and_see_all_drafts(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    admin = signed_in(db, Role.ADMINISTRATOR, "admin")
    event_id = create(client, owner).json()["id"]
    assert client.patch(
        f"/api/v1/events/{event_id}", headers=admin, json={"name": "Admin edit"}
    ).status_code == 200
    response = client.get("/api/v1/owner/events", headers=admin)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_owner_list_is_private_and_paginated(client, db):
    a = signed_in(db, Role.EVENT_OWNER, "owner_a")
    b = signed_in(db, Role.EVENT_OWNER, "owner_b")
    for _ in range(3):
        assert create(client, a).status_code == 201
    assert create(client, b).status_code == 201
    first = client.get("/api/v1/owner/events?limit=2&offset=0", headers=a).json()
    second = client.get("/api/v1/owner/events?limit=2&offset=2", headers=a).json()
    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert client.get("/api/v1/owner/events").status_code == 401
    assert client.get("/api/v1/owner/events?limit=101", headers=a).status_code == 422


def test_drafts_never_appear_in_public_catalog(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    event_id = create(client, owner, venue="Sala", **dates()).json()["id"]
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 20, "offset": 0, "total": 0}
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404


def test_publish_requires_ticket_zones_and_does_not_mutate(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    event_id = create(client, owner, venue="Sala", **dates()).json()["id"]
    response = client.post(f"/api/v1/events/{event_id}/publish", headers=owner)
    assert response.status_code == 422
    assert "zones" in response.json()["detail"].lower()
    assert db.get(Event, UUID(event_id)).status == EventStatus.DRAFT
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404


def test_incomplete_event_cannot_publish(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    event_id = create(client, owner).json()["id"]
    response = client.post(f"/api/v1/events/{event_id}/publish", headers=owner)
    assert response.status_code == 422
    assert "details" in response.json()["detail"]
    assert db.get(Event, UUID(event_id)).status == "draft"


def test_invalid_dates_payloads_and_readonly_fields(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    assert create(client, owner, start_at="2027-01-01T12:00:00").status_code == 422
    assert create(client, owner, owner_id="00000000-0000-0000-0000-000000000001").status_code == 422
    d = dates()
    assert create(client, owner, start_at=d["end_at"], end_at=d["start_at"]).status_code == 422
    assert db.scalar(select(func.count()).select_from(Event)) == 0


def test_unpublish_rejected_until_inventoried(client, db):
    owner = signed_in(db, Role.EVENT_OWNER, "owner")
    event_id = create(client, owner).json()["id"]
    assert client.post(f"/api/v1/events/{event_id}/unpublish", headers=owner).status_code == 409
    assert db.get(Event, UUID(event_id)).status == "draft"
