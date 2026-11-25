"""Protected internal gate commands; real DB migrations are verified in CI."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ticketing_service.main import app
from ticketing_service.persistence import Base, SaleGateRow
from ticketing_service.sale_http import session_scope
from ticketing_service.settings import settings

SECRET = "test-only-service-credential-32-characters-long"


@pytest.fixture
def environment(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def test_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = test_session
    monkeypatch.setattr(settings, "sale_commands_enabled", True)
    monkeypatch.setattr(settings, "events_internal_token", SECRET)
    with TestClient(app) as client:
        try:
            yield client, engine
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def auth():
    return {"X-Internal-Service-Token": SECRET}


def seed(engine, event_id):
    with Session(engine) as db:
        db.add(SaleGateRow(
            event_id=event_id, state="closed", version=0, event_revision=0,
        ))
        db.commit()


def test_commands_are_disabled_by_default(environment, monkeypatch):
    client, _ = environment
    monkeypatch.setattr(settings, "sale_commands_enabled", False)
    response = client.get(f"/api/v1/internal/sales/gates/{uuid4()}", headers=auth())
    assert response.status_code == 404


def test_private_credential_is_required(environment):
    client, engine = environment
    event_id = uuid4()
    seed(engine, event_id)
    url = f"/api/v1/internal/sales/gates/{event_id}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"X-Internal-Service-Token": "wrong"}).status_code == 401
    assert client.post(
        url + "/commands", json={
            "command_id": str(uuid4()), "action": "open",
            "expected_version": 0, "event_revision": 1,
        },
    ).status_code == 401


def test_open_close_and_duplicate_replay(environment):
    client, engine = environment
    event_id = uuid4()
    seed(engine, event_id)
    url = f"/api/v1/internal/sales/gates/{event_id}"
    open_cmd = {
        "command_id": str(uuid4()), "action": "open",
        "expected_version": 0, "event_revision": 1,
    }
    opened = client.post(url + "/commands", json=open_cmd, headers=auth())
    assert opened.status_code == 200, opened.text
    assert opened.json()["state"] == "open" and opened.json()["version"] == 1
    replay = client.post(url + "/commands", json=open_cmd, headers=auth())
    assert replay.status_code == 200 and replay.json() == opened.json()
    close_cmd = {
        "command_id": str(uuid4()), "action": "close",
        "expected_version": 1, "event_revision": 1,
    }
    closed = client.post(url + "/commands", json=close_cmd, headers=auth())
    assert closed.status_code == 200 and closed.json()["state"] == "closed"
    assert closed.json()["version"] == 2
    assert client.get(url, headers=auth()).json()["state"] == "closed"
    assert client.post(url + "/commands", json=open_cmd | {
        "command_id": str(uuid4()),
    }, headers=auth()).status_code == 409


def test_unknown_gate_is_closed_and_cannot_open(environment):
    client, _ = environment
    url = f"/api/v1/internal/sales/gates/{uuid4()}"
    status = client.get(url, headers=auth())
    assert status.status_code == 200
    assert status.json()["state"] == "closed"
    response = client.post(url + "/commands", json={
        "command_id": str(uuid4()), "action": "open",
        "expected_version": 0, "event_revision": 1,
    }, headers=auth())
    assert response.status_code == 409


def test_colliding_idempotency_key_rejected(environment):
    client, engine = environment
    event_id, command_id = uuid4(), uuid4()
    seed(engine, event_id)
    url = f"/api/v1/internal/sales/gates/{event_id}/commands"
    command = {"command_id": str(command_id), "action": "open",
               "expected_version": 0, "event_revision": 1}
    assert client.post(url, json=command, headers=auth()).status_code == 200
    assert client.post(url, json=command | {"action": "close"},
                       headers=auth()).status_code == 409
