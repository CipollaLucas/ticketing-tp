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
