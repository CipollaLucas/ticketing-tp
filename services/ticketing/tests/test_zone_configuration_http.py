"""H5 zone creation: contract validation, authorization and local atomicity."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ticketing_service.inventory_http import inventory_session
from ticketing_service.main import app
from ticketing_service.persistence import Base, SaleGateRow, SeatRow, ZoneRow
from ticketing_service.settings import settings
from ticketing_service.zone_configuration_http import draft_verifier


class OwnerVerifierStub:
    def __init__(self):
        self.allowed = True
        self.calls = []

    def require_owner_draft(self, event_id, token, request_id):
        self.calls.append((event_id, token))
        if not self.allowed:
            raise HTTPException(404, "Event unavailable")


@pytest.fixture
def scenario(monkeypatch):
    db_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(db_engine)
    owner = OwnerVerifierStub()
    monkeypatch.setattr(settings, "zone_configuration_enabled", True)

    def sessions():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[inventory_session] = sessions
    app.dependency_overrides[draft_verifier] = lambda: owner
    try:
        with TestClient(app) as client:
            yield client, db_engine, owner, uuid4()
    finally:
        app.dependency_overrides.clear()
        db_engine.dispose()


def post(client, event_id, payload, token=True):
    headers = {"Authorization": "Bearer valid"} if token else {}
    return client.post(f"/api/v1/events/{event_id}/zones", json=payload, headers=headers)


def general(name="General"):
    return {
        "name": name,
        "mode": "general",
        "price_minor": 2500,
        "currency": "ARS",
        "capacity": 20,
        "seats": [],
    }


def numbered():
    return {
        "name": "VIP",
        "mode": "numbered",
        "price_minor": 5500,
        "currency": "ARS",
        "seats": [{"label": "A1"}, {"label": "A2"}],
    }


def test_create_general_and_numbered_zones(scenario):
    client, engine, owner, event_id = scenario
    response = post(client, event_id, general())
    assert response.status_code == 201, response.text
    assert response.json()["available"] == 20
    assert response.json()["seats"] == []
    assert response.headers["cache-control"] == "no-store"
    numbered_result = post(client, event_id, numbered())
    assert numbered_result.status_code == 201, numbered_result.text
    assert numbered_result.json()["available"] == 2
    assert [s["label"] for s in numbered_result.json()["seats"]] == ["A1", "A2"]
    assert len(owner.calls) == 2
    with Session(engine) as db:
        assert len(db.scalars(select(ZoneRow)).all()) == 2
        assert len(db.scalars(select(SeatRow)).all()) == 2


def test_different_customer_and_duplicates_cannot_create_zone(scenario):
    client, engine, owner, event_id = scenario
    owner.allowed = False
    assert post(client, event_id, general()).status_code == 404
    with Session(engine) as db:
        assert db.scalars(select(ZoneRow)).all() == []
    owner.allowed = True
    assert post(client, event_id, general()).status_code == 201
    assert post(client, event_id, general()).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"name": "A", "mode": "general", "price_minor": 1, "currency": "ARS"},
        {"name": "A", "mode": "numbered", "price_minor": 1, "currency": "ARS"},
        {
            "name": "A",
            "mode": "numbered",
            "price_minor": 1,
            "currency": "ARS",
            "seats": [{"label": "A1"}, {"label": "A1"}],
        },
        {
            "name": "A",
            "mode": "general",
            "price_minor": 1,
            "currency": "ARS",
            "capacity": 4,
            "unexpected": True,
        },
    ],
)
def test_invalid_requests_do_not_write(scenario, body):
    client, engine, _, event_id = scenario
    assert post(client, event_id, body).status_code == 422
    with Session(engine) as db:
        assert db.scalars(select(ZoneRow)).all() == []


def test_disabled_or_missing_bearer_cannot_write(scenario, monkeypatch):
    client, engine, owner, event_id = scenario
    monkeypatch.setattr(settings, "zone_configuration_enabled", False)
    assert post(client, event_id, general()).status_code == 404
    monkeypatch.setattr(settings, "zone_configuration_enabled", True)
    assert post(client, event_id, general(), token=False).status_code == 401
    assert owner.calls == []
    with Session(engine) as db:
        assert db.scalars(select(ZoneRow)).all() == []


def test_first_zone_provisions_closed_gate_without_opening_sales(scenario):
    client, engine, _, event_id = scenario
    assert post(client, event_id, general()).status_code == 201
    with Session(engine) as db:
        gate = db.get(SaleGateRow, event_id)
        assert gate is not None
        assert (gate.state, gate.version, gate.event_revision) == ("closed", 0, 0)


def test_already_open_gate_cannot_be_reset_by_new_zone(scenario):
    client, engine, _, event_id = scenario
    with Session(engine) as db:
        db.add(SaleGateRow(event_id=event_id, state="open", version=5, event_revision=4))
        db.commit()
    result = post(client, event_id, general())
    assert result.status_code == 409
    with Session(engine) as db:
        gate = db.get(SaleGateRow, event_id)
        assert gate is not None
        assert (gate.state, gate.version, gate.event_revision) == ("open", 5, 4)
        assert db.scalars(select(ZoneRow)).all() == []


def test_closed_existing_gate_is_preserved_on_zone_creation(scenario):
    client, engine, _, event_id = scenario
    with Session(engine) as db:
        db.add(SaleGateRow(event_id=event_id, state="closed", version=2, event_revision=2))
        db.commit()
    assert post(client, event_id, general()).status_code == 201
    with Session(engine) as db:
        gate = db.get(SaleGateRow, event_id)
        assert gate is not None
        assert (gate.state, gate.version, gate.event_revision) == ("closed", 2, 2)
