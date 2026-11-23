"""HTTP contracts: real Bearer authentication and persisted event state."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.auth import token_digest
from app.models import AuthSession, Role, User


@pytest.fixture
def actors(db):
    result = {}
    for name, role in (
        ("owner", Role.EVENT_OWNER), ("other", Role.EVENT_OWNER),
        ("admin", Role.ADMINISTRATOR), ("customer", Role.CUSTOMER),
    ):
        user = User(username=name, display_name=name, password_hash="unused", role=role.value)
        db.add(user)
        db.flush()
        token = f"event-test-session-{name}"
        db.add(AuthSession(
            token_hash=token_digest(token), user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ))
        result[name] = (user.id, {"Authorization": f"Bearer {token}"})
    db.commit()
    return result


def payload(**overrides):
    start = datetime.now(UTC) + timedelta(days=10)
    return {
        "name": " Noche de bandas ", "description": "Música local",
        "venue": " Centro Cultural ", "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=2)).isoformat(), **overrides,
    }


def create(client, actors, actor="owner", **overrides):
    response = client.post("/api/v1/events", headers=actors[actor][1], json=payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_draft_assigns_identity_and_hides_from_public(client, actors):
    event = create(client, actors)
    assert event["owner_id"] == str(actors["owner"][0])
    assert event["name"] == "Noche de bandas"
    assert event["venue"] == "Centro Cultural"
    assert event["status"] == "draft"
    assert "zones" not in event
    assert client.get(f"/api/v1/events/{event['id']}").status_code == 404
    assert client.get("/api/v1/events").json() == {
        "items": [], "limit": 20, "offset": 0, "total": 0,
    }
    page = client.get("/api/v1/owner/events", headers=actors["owner"][1]).json()
    assert [item["id"] for item in page["items"]] == [event["id"]]


@pytest.mark.parametrize("actor,status", [(None, 401), ("customer", 403)])
@pytest.mark.parametrize("method,path", [
    ("post", "/events"), ("patch", "/events/{id}"),
    ("post", "/events/{id}/publish"), ("post", "/events/{id}/unpublish"),
    ("get", "/owner/events"),
])
def test_writes_and_owner_listing_require_role(client, actors, actor, status, method, path):
    path = "/api/v1" + path.format(id=uuid4())
    kwargs = {"headers": actors[actor][1] if actor else {}}
    if method != "get":
        kwargs["json"] = payload() if path == "/api/v1/events" else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == status
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("changes", [
    {"name": " "}, {"venue": " "}, {"name": "a" * 201}, {"description": "a" * 5001},
    {"start_at": "2020-01-01T10:00:00Z"}, {"start_at": "2030-01-01T10:00:00"},
    {"end_at": "2020-01-01T10:00:00Z"}, {"owner_id": str(uuid4())},
    {"status": "published"}, {"capacity": 100}, {"name": None},
])
def test_invalid_create_does_not_persist(client, actors, changes):
    response = client.post("/api/v1/events", headers=actors["owner"][1], json=payload(**changes))
    assert response.status_code == 422
    assert client.get("/api/v1/owner/events", headers=actors["owner"][1]).json()["total"] == 0


@pytest.mark.parametrize("method,suffix,body", [
    ("patch", "", {"name": "Stolen"}), ("post", "/publish", {}),
    ("post", "/unpublish", {}),
])
def test_foreign_owner_denied_and_admin_can_manage(client, actors, method, suffix, body):
    event = create(client, actors)
    path = f"/api/v1/events/{event['id']}{suffix}"
    assert getattr(client, method)(path, headers=actors["other"][1], json=body).status_code == 403
    stored = client.get("/api/v1/owner/events", headers=actors["owner"][1]).json()["items"][0]
    assert stored == event
    response = getattr(client, method)(path, headers=actors["admin"][1], json=body)
    assert response.status_code == 200
    assert response.json()["owner_id"] == event["owner_id"]


@pytest.mark.parametrize("changes", [
    {}, {"name": None}, {"description": None}, {"venue": " "},
    {"owner_id": str(uuid4())}, {"status": "published"},
    {"end_at": "2020-01-01T10:00:00Z"}, {"start_at": "2030-01-01T10:00:00"},
])
def test_invalid_partial_update_is_atomic(client, actors, changes):
    event = create(client, actors)
    response = client.patch(
        f"/api/v1/events/{event['id']}", headers=actors["owner"][1], json=changes,
    )
    assert response.status_code == 422
    assert client.get("/api/v1/owner/events", headers=actors["owner"][1]).json()["items"] == [event]


def test_publication_lifecycle_without_inventory(client, actors):
    event = create(client, actors, description="")
    path = f"/api/v1/events/{event['id']}"
    auth = actors["owner"][1]
    assert client.post(path + "/publish", headers=auth, json={}).status_code == 422
    assert client.get(path).status_code == 404
    response = client.patch(path, headers=auth, json={"description": "Concierto"})
    assert response.status_code == 200
    assert response.json()["name"] == event["name"]
    response = client.post(path + "/publish", headers=auth, json={})
    assert response.status_code == 200
    published = response.json()
    assert published["status"] == "published"
    assert client.get(path).json() == published
    assert client.post(path + "/publish", headers=auth, json={}).json() == published
    assert client.patch(path, headers=auth, json={"name": "Changed"}).status_code == 409
    assert client.post(path + "/unpublish", headers=auth, json={}).json()["status"] == "draft"
    assert client.post(path + "/unpublish", headers=auth, json={}).status_code == 200
    assert client.get(path).status_code == 404
    assert client.patch(path, headers=auth, json={"name": "Changed"}).status_code == 200


@pytest.mark.parametrize("suffix", ["", "/publish", "/unpublish"])
def test_unknown_event_returns_404(client, actors, suffix):
    path = f"/api/v1/events/{uuid4()}{suffix}"
    method = client.post if suffix else client.patch
    body = {} if suffix else {"name": "Missing"}
    assert method(path, headers=actors["owner"][1], json=body).status_code == 404


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_pagination_validation(client, actors, query):
    assert client.get("/api/v1/events?" + query).status_code == 422
    assert client.get("/api/v1/owner/events?" + query, headers=actors["owner"][1]).status_code == 422


def test_catalog_order_total_visibility_and_owner_scope(client, actors, db):
    from app.models import Event

    same = payload()
    first = create(client, actors, **same)
    second = create(client, actors, actor="other", **same)
    draft = create(client, actors)
    past = create(client, actors)
    for item in (first, second, past):
        assert client.post(
            f"/api/v1/events/{item['id']}/publish", headers=actors["admin"][1], json={},
        ).status_code == 200
    stored = db.get(Event, UUID(past["id"]))
    stored.start_at = datetime.now(UTC) - timedelta(days=2)
    stored.end_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    expected = sorted([first["id"], second["id"]])
    page = client.get("/api/v1/events?limit=1&offset=1").json()
    assert page["total"] == 2
    assert [item["id"] for item in page["items"]] == expected[1:]
    assert page["limit"] == 1 and page["offset"] == 1
    assert client.get("/api/v1/events?offset=100").json()["items"] == []
    assert client.get(f"/api/v1/events/{past['id']}").status_code == 200
    assert client.get(f"/api/v1/events/{draft['id']}").status_code == 404
    own = client.get("/api/v1/owner/events", headers=actors["other"][1]).json()
    assert own["total"] == 1 and own["items"][0]["id"] == second["id"]
    assert client.get("/api/v1/owner/events", headers=actors["admin"][1]).json()["total"] == 4


def test_date_offsets_are_normalized_to_utc(client, actors):
    event = create(
        client, actors, start_at="2040-01-01T20:00:00-03:00", end_at="2040-01-02T01:00:00Z",
    )
    assert event["start_at"] == "2040-01-01T23:00:00Z"
    assert event["end_at"] == "2040-01-02T01:00:00Z"


@pytest.mark.parametrize("suffix", ["publish", "unpublish"])
def test_transitions_reject_extra_fields(client, actors, suffix):
    event = create(client, actors)
    response = client.post(
        f"/api/v1/events/{event['id']}/{suffix}", headers=actors["owner"][1],
        json={"owner_id": str(actors["other"][0])},
    )
    assert response.status_code == 422
    assert client.get("/api/v1/owner/events", headers=actors["owner"][1]).json()["items"] == [event]


def test_past_draft_cannot_be_published(client, actors, db):
    from app.models import Event

    event = create(client, actors)
    stored = db.get(Event, UUID(event["id"]))
    stored.start_at = datetime.now(UTC) - timedelta(days=2)
    stored.end_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    response = client.post(
        f"/api/v1/events/{event['id']}/publish", headers=actors["owner"][1], json={},
    )
    assert response.status_code == 422
    db.refresh(stored)
    assert stored.status == "draft"


def test_revoked_owner_cannot_mutate_with_existing_session(client, actors, db):
    event = create(client, actors)
    owner = db.get(User, actors["owner"][0])
    owner.role = Role.CUSTOMER.value
    db.commit()
    response = client.patch(
        f"/api/v1/events/{event['id']}", headers=actors["owner"][1], json={"name": "Changed"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("changes", [
    {"name": "Bad\x00name"}, {"venue": "Bad\x00venue"}, {"description": "Bad\x00description"},
    {"end_at": "9999-12-31T23:59:59-23:59"},
    {"start_at": "0001-01-01T00:00:00+23:59"},
])
def test_unstorable_metadata_returns_422_without_mutation(client, actors, changes):
    event = create(client, actors)
    response = client.post("/api/v1/events", headers=actors["owner"][1], json=payload(**changes))
    assert response.status_code == 422
    response = client.patch(
        f"/api/v1/events/{event['id']}", headers=actors["owner"][1], json=changes,
    )
    assert response.status_code == 422
    assert client.get("/api/v1/owner/events", headers=actors["owner"][1]).json()["items"] == [event]
