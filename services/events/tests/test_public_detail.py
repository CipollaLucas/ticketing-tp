"""Stage I public event detail behavior, isolated from Legacy and Identity."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.application import public_event_detail
from events_service.main import app, session_scope
from events_service.persistence import Base, EventRow, SqlAlchemyEventReader


@pytest.fixture
def isolated():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    ids = {"upcoming": uuid4(), "past": uuid4(), "draft": uuid4()}
    with Session(engine) as db:
        for kind, start, status in (
            ("upcoming", now + timedelta(days=2), "published"),
            ("past", now - timedelta(days=2), "published"),
            ("draft", now + timedelta(days=2), "draft"),
        ):
            db.add(EventRow(
                id=ids[kind], owner_id=uuid4(),
                name=f"Event {kind}", description="Description",
                venue="Hall", start_at=start,
                end_at=start + timedelta(hours=2), status=status,
            ))
        db.commit()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = session
    try:
        with TestClient(app) as client:
            yield client, engine, ids
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_published_upcoming_detail_matches_legacy_visibility(isolated):
    client, _, ids = isolated
    response = client.get(f"/api/v1/events/{ids['upcoming']}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == str(ids["upcoming"])
    assert data["status"] == "published"
    assert data["name"] == "Event upcoming"
    assert data["venue"] == "Hall"


def test_published_past_detail_still_public_but_absent_from_catalog(isolated):
    client, _, ids = isolated
    detail = client.get(f"/api/v1/events/{ids['past']}")
    assert detail.status_code == 200, detail.text
    catalog = client.get("/api/v1/events")
    assert catalog.status_code == 200
    assert [item["id"] for item in catalog.json()["items"]] == [str(ids["upcoming"])]


def test_draft_and_missing_indistinguishable(isolated):
    client, _, ids = isolated
    hidden = client.get(f"/api/v1/events/{ids['draft']}")
    missing = client.get(f"/api/v1/events/{uuid4()}")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json() == {"detail": "Event not found"}


def test_invalid_uuid_is_422(isolated):
    client, _, _ = isolated
    assert client.get("/api/v1/events/not-a-uuid").status_code == 422


def test_public_detail_application_does_not_accept_draft(isolated):
    _, engine, ids = isolated
    with Session(engine) as db:
        repo = SqlAlchemyEventReader(db)
        assert public_event_detail(repo, ids["draft"]) is None
        assert public_event_detail(repo, ids["upcoming"]) is not None
        assert public_event_detail(repo, uuid4()) is None
