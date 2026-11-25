"""Private no-sales close contract; real Events and purchases remain untouched."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ticketing_service.main import app
from ticketing_service.persistence import Base, OrderRow, SaleGateRow
from ticketing_service.sale_http import session_scope
from ticketing_service.settings import settings

SECRET = "test-only-service-credential-32-characters-long"


@pytest.fixture
def context(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    event_id = uuid4()
    with Session(engine) as db:
        db.add(
            SaleGateRow(
                event_id=event_id,
                state="open",
                version=1,
                event_revision=1,
            )
        )
        db.commit()

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[session_scope] = session
    monkeypatch.setattr(settings, "sale_commands_enabled", True)
    monkeypatch.setattr(settings, "events_internal_token", SECRET)
    try:
        with TestClient(app) as client:
            yield client, engine, event_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def endpoint(event_id):
    return f"/api/v1/internal/sales/gates/{event_id}/close-without-sales"


def payload():
    return {
        "command_id": str(uuid4()),
        "action": "close",
        "expected_version": 1,
        "event_revision": 1,
    }


def headers():
    return {"X-Internal-Service-Token": SECRET}


def test_close_without_sales_is_atomic_and_idempotent(context):
    client, engine, event_id = context
    command = payload()
    response = client.post(endpoint(event_id), headers=headers(), json=command)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "closed"
    assert response.json()["version"] == 2
    replay = client.post(endpoint(event_id), headers=headers(), json=command)
    assert replay.status_code == 200 and replay.json() == response.json()
    with Session(engine) as db:
        assert db.get(SaleGateRow, event_id).state == "closed"


def test_order_prevents_close_and_keeps_gate_open(context):
    client, engine, event_id = context
    with Session(engine) as db:
        db.add(
            OrderRow(
                id=uuid4(),
                customer_id=uuid4(),
                event_id=event_id,
                idempotency_key="test-order",
                request_hash="a" * 64,
                total_minor=100,
                currency="ARS",
                status="confirmed",
            )
        )
        db.commit()
    result = client.post(endpoint(event_id), headers=headers(), json=payload())
    assert result.status_code == 409
    assert result.json()["detail"] == "Cannot unpublish an event with sales"
    with Session(engine) as db:
        assert db.get(SaleGateRow, event_id).state == "open"


def test_wrong_action_or_stale_cas_cannot_change_gate(context):
    client, engine, event_id = context
    wrong = payload() | {"action": "open"}
    assert client.post(endpoint(event_id), headers=headers(), json=wrong).status_code == 422
    stale = payload() | {"expected_version": 0}
    assert client.post(endpoint(event_id), headers=headers(), json=stale).status_code == 409
    with Session(engine) as db:
        assert db.get(SaleGateRow, event_id).state == "open"


def test_no_token_unknown_gate_and_flag_disabled_fail_closed(context, monkeypatch):
    client, engine, event_id = context
    assert client.post(endpoint(event_id), json=payload()).status_code == 401
    assert client.post(endpoint(uuid4()), headers=headers(), json=payload()).status_code == 409
    monkeypatch.setattr(settings, "sale_commands_enabled", False)
    assert client.post(endpoint(event_id), headers=headers(), json=payload()).status_code == 404
    with Session(engine) as db:
        assert db.get(SaleGateRow, event_id).state == "open"
