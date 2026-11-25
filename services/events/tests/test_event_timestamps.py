"""Stage I timestamp shape and persistence through Events-owned adapters."""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from events_service.commands import identity_port
from events_service.commands import session_scope as command_scope
from events_service.identity import Principal
from events_service.main import app, session_scope
from events_service.persistence import Base, EventRow
from events_service.settings import settings

OWNER = uuid4()
EXPECTED = {
    "id", "owner_id", "name", "description", "venue",
    "start_at", "end_at", "status", "created_at", "updated_at",
}


class IdentityStub:
    def introspect(self, token, request_id=None):
        assert token == "test-auth"
        return Principal(OWNER, "owner", "event_owner")


def test_public_catalog_detail_and_protected_draft_include_legacy_timestamps(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def db_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = db_session
    app.dependency_overrides[command_scope] = db_session
    app.dependency_overrides[identity_port] = lambda: IdentityStub()
    monkeypatch.setattr(settings, "protected_drafts_enabled", True)

    now = datetime.now(UTC)
    event_id = uuid4()
    original_time = now - timedelta(days=5)
    with Session(engine) as db:
        db.add(EventRow(
            id=event_id, owner_id=OWNER, name="Published",
            description="Good", venue="Venue",
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=5, hours=2),
            status="published",
            created_at=original_time, updated_at=original_time,
        ))
        db.commit()
    try:
        with TestClient(app) as client:
            catalog = client.get("/api/v1/events")
            assert catalog.status_code == 200, catalog.text
            published = catalog.json()["items"][0]
            assert set(published) == EXPECTED
            assert datetime.fromisoformat(published["created_at"]).year == original_time.year

            detail = client.get(f"/api/v1/events/{event_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json() == published

            start = now + timedelta(days=7)
            created = client.post(
                "/api/v1/events",
                headers={"Authorization": "Bearer test-auth"},
                json={
                    "name": "Draft", "description": "", "venue": "Hall",
                    "start_at": start.isoformat(),
                    "end_at": (start + timedelta(hours=2)).isoformat(),
                },
            )
            assert created.status_code == 201, created.text
            draft = created.json()
            assert set(draft) == EXPECTED
            assert draft["created_at"] == draft["updated_at"]
            listing = client.get(
                "/api/v1/owner/events",
                headers={"Authorization": "Bearer test-auth"},
            )
            assert listing.status_code == 200, listing.text
            assert all(set(row) == EXPECTED for row in listing.json()["items"])
            assert any(row["id"] == draft["id"] for row in listing.json()["items"])
            with Session(engine) as db:
                persisted = db.get(EventRow, UUID(draft["id"]))
                assert persisted is not None and persisted.created_at == persisted.updated_at
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
