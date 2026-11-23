"""PostgreSQL checks: set TEST_POSTGRES_URL to an isolated test server.

Each test creates a unique temporary schema and drops only that schema.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from app.auth import Credentials, Db, get_current_user, router
from app.database import Base, get_db
from app.models import AuthSession, Role, User


@pytest.fixture
def postgres_engine():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL not set; real PostgreSQL check not executed")
    root_engine = create_engine(url)
    schema = f"auth_test_{uuid4().hex}"
    with root_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield engine
    finally:
        engine.dispose()
        with root_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        root_engine.dispose()


def test_postgres_migration_roundtrip(postgres_engine):
    from pathlib import Path

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import inspect

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with postgres_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert {"users", "auth_sessions"} <= set(inspect(connection).get_table_names())
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        connection.rollback()
        command.downgrade(config, "base")
        assert not {"users", "auth_sessions"} & set(inspect(connection).get_table_names())
        connection.rollback()
        command.upgrade(config, "head")


def test_concurrent_admin_demotions_preserve_an_administrator(postgres_engine):
    Base.metadata.create_all(postgres_engine)
    with Session(postgres_engine) as db:
        users = [
            User(
                username=name,
                display_name=name,
                password_hash="not-used-in-test",
                role=Role.ADMINISTRATOR,
            )
            for name in ("admin_a", "admin_b")
        ]
        db.add_all(users)
        db.flush()
        ids = [user.id for user in users]
        tokens = ["session-a-for-test", "session-b-for-test"]
        for user, token in zip(users, tokens, strict=True):
            db.add(
                AuthSession(
                    token_hash=sha256(token.encode()).hexdigest(),
                    user_id=user.id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        db.commit()
    barrier = Barrier(2)
    app = FastAPI()
    app.include_router(router)

    def test_db():
        with Session(postgres_engine) as db:
            yield db

    def authenticated_before_race(db: Db, credentials: Credentials):
        user = get_current_user(db, credentials)
        barrier.wait(timeout=10)
        return user

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_user] = authenticated_before_race

    def demote_other(index):
        with TestClient(app) as client:
            return client.patch(
                f"/api/v1/admin/users/{ids[1 - index]}/role",
                headers={"Authorization": f"Bearer {tokens[index]}"},
                json={"role": "customer"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(demote_other, (0, 1)))
    assert sorted(results) == [200, 403]
    with Session(postgres_engine) as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.role == Role.ADMINISTRATOR))
            == 1
        )


def test_identity_flow_on_migrated_postgres(postgres_engine):
    from pathlib import Path

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with postgres_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    app = FastAPI()
    app.include_router(router)

    def test_db():
        with Session(postgres_engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        payload = {
            "username": "postgres_user",
            "display_name": "Postgres User",
            "password": "test-postgres-passphrase-2026",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        assert response.json()["role"] == "customer"
        response = client.post(
            "/api/v1/auth/login",
            json={"username": payload["username"], "password": payload["password"]},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        auth = {"Authorization": f"Bearer {response.json()['access_token']}"}
        response = client.get("/api/v1/auth/me", headers=auth)
        assert response.status_code == 200
        assert response.json()["username"] == "postgres_user"
        assert client.post("/api/v1/auth/logout", headers=auth).status_code == 204
        assert client.get("/api/v1/auth/me", headers=auth).status_code == 401


def test_event_migration_on_postgres(postgres_engine):
    from test_event_migrations import assert_event_migration

    assert_event_migration(postgres_engine)


def test_event_http_flow_on_migrated_postgres(postgres_engine):
    from pathlib import Path

    from app.events import router as events_router

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with postgres_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    app = FastAPI()
    app.include_router(router)
    app.include_router(events_router)

    def test_db():
        with Session(postgres_engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={
            "username": "events_owner", "display_name": "Owner",
            "password": "test-events-passphrase-2026",
        })
        assert response.status_code == 201
        user_id = response.json()["id"]
        with Session(postgres_engine) as db:
            from uuid import UUID

            owner = db.get(User, UUID(user_id))
            owner.role = Role.EVENT_OWNER.value
            db.commit()
        response = client.post("/api/v1/auth/login", json={
            "username": "events_owner", "password": "test-events-passphrase-2026",
        })
        assert response.status_code == 200
        auth = {"Authorization": f"Bearer {response.json()['access_token']}"}
        start = datetime.now(UTC) + timedelta(days=20)
        response = client.post("/api/v1/events", headers=auth, json={
            "name": "Concierto", "description": "Música", "venue": "Centro Cultural",
            "start_at": start.isoformat(), "end_at": (start + timedelta(hours=2)).isoformat(),
        })
        assert response.status_code == 201, response.text
        path = f"/api/v1/events/{response.json()['id']}"
        assert client.get(path).status_code == 404
        assert client.patch(path, headers=auth, json={"venue": "Teatro"}).status_code == 200
        response = client.post(path + "/publish", headers=auth, json={})
        assert response.status_code == 200
        assert response.json()["start_at"].endswith("Z")
        assert client.get("/api/v1/events").json()["total"] == 1
        assert client.get(path).json()["venue"] == "Teatro"
        assert client.post(path + "/unpublish", headers=auth, json={}).status_code == 200
        assert client.get(path).status_code == 404
        for field in ("name", "venue", "description"):
            invalid = {field: "bad\x00text"}
            response = client.post("/api/v1/events", headers=auth, json={
                "name": "New", "description": "Music", "venue": "Hall",
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=2)).isoformat(), **invalid,
            })
            assert response.status_code == 422
            assert client.patch(path, headers=auth, json=invalid).status_code == 422
        stored = client.get("/api/v1/owner/events", headers=auth).json()
        assert stored["total"] == 1
        assert stored["items"][0]["venue"] == "Teatro"


@pytest.mark.parametrize("intervening_change,expected", [("publish", 409), ("revoke", 403)])
def test_event_update_rechecks_after_postgres_lock(postgres_engine, intervening_change, expected):
    from threading import Event as Signal
    from time import monotonic, sleep

    from sqlalchemy import text

    from app.events import router as events_router
    from app.models import Event

    Base.metadata.create_all(postgres_engine)
    token = "event-race-session"
    start = datetime.now(UTC) + timedelta(days=10)
    with Session(postgres_engine) as db:
        owner = User(
            username="race_owner", display_name="Owner", password_hash="unused",
            role=Role.EVENT_OWNER.value,
        )
        db.add(owner)
        db.flush()
        event = Event(
            owner_id=owner.id, name="Original", description="Music", venue="Hall",
            start_at=start, end_at=start + timedelta(hours=2),
        )
        db.add_all([event, AuthSession(
            token_hash=sha256(token.encode()).hexdigest(), user_id=owner.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )])
        db.commit()
        owner_id, event_id = owner.id, event.id

    authenticated = Signal()
    test_app = FastAPI()
    test_app.include_router(events_router)

    def test_db():
        with Session(postgres_engine) as db:
            db.execute(text("SET application_name = 'ticketing-event-race'"))
            yield db

    def authenticate_and_load_stale_event(db: Db, credentials: Credentials):
        user = get_current_user(db, credentials)
        # Retain an outdated object to catch missing populate_existing after waiting.
        db.info["loaded_event"] = db.get(Event, event_id)
        authenticated.set()
        return user

    test_app.dependency_overrides[get_db] = test_db
    test_app.dependency_overrides[get_current_user] = authenticate_and_load_stale_event

    def update_request():
        with TestClient(test_app) as client:
            return client.patch(
                f"/api/v1/events/{event_id}", json={"name": "Changed"},
                headers={"Authorization": f"Bearer {token}"},
            ).status_code

    with Session(postgres_engine) as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        event = blocker.scalar(select(Event).where(Event.id == event_id).with_for_update())
        future = executor.submit(update_request)
        try:
            assert authenticated.wait(timeout=5), "Request did not authenticate"
            deadline = monotonic() + 5
            waiting = False
            while monotonic() < deadline and not future.done():
                with postgres_engine.connect() as observer:
                    waiting = observer.scalar(text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE application_name = 'ticketing-event-race' "
                        "AND wait_event_type = 'Lock'"
                    )) > 0
                if waiting:
                    break
                sleep(0.01)
            assert waiting, "Event mutation did not wait for the PostgreSQL row lock"
            if intervening_change == "publish":
                event.status = "published"
            else:
                blocker.get(User, owner_id).role = Role.CUSTOMER.value
            blocker.commit()
            assert future.result(timeout=5) == expected
        finally:
            blocker.rollback()
    with Session(postgres_engine) as db:
        event = db.get(Event, event_id)
        assert event.name == "Original"
        assert event.status == ("published" if intervening_change == "publish" else "draft")
