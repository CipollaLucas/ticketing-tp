"""Private provisioning HTTP proof without touching persistent PostgreSQL."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ticketing_service.domain import GateState
from ticketing_service.main import app
from ticketing_service.provision_http import provision_unit
from ticketing_service.settings import settings

SECRET = "test-only-events-gate-provision-secret-12345"


class StubProvision:
    def __init__(self):
        self.gates = {}
        self.commits = 0
        self.rollbacks = 0

    def ensure_closed_gate(self, event_id):
        return self.gates.setdefault(event_id, GateState(event_id, "closed", 0, 0))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def isolated(monkeypatch):
    unit = StubProvision()
    app.dependency_overrides[provision_unit] = lambda: unit
    monkeypatch.setattr(settings, "gate_provisioning_enabled", True)
    monkeypatch.setattr(settings, "events_internal_token", SECRET)
    try:
        with TestClient(app) as client:
            yield client, unit
    finally:
        app.dependency_overrides.clear()


def endpoint(event_id):
    return f"/api/v1/internal/sales/gates/{event_id}/provision"


def auth():
    return {"X-Internal-Service-Token": SECRET}


def test_off_by_default_even_with_correct_token(isolated, monkeypatch):
    client, unit = isolated
    monkeypatch.setattr(settings, "gate_provisioning_enabled", False)
    assert client.put(endpoint(uuid4()), headers=auth()).status_code == 404
    assert not unit.gates


def test_missing_wrong_or_short_credential_rejected(isolated, monkeypatch):
    client, unit = isolated
    address = endpoint(uuid4())
    assert client.put(address).status_code == 401
    assert client.put(address, headers={"X-Internal-Service-Token": "bad"}).status_code == 401
    monkeypatch.setattr(settings, "events_internal_token", "")
    assert client.put(address, headers=auth()).status_code == 503
    assert not unit.gates


def test_first_provision_creates_closed_gate_and_retries_preserve_existing(isolated):
    client, unit = isolated
    event_id = uuid4()
    first = client.put(endpoint(event_id), headers=auth())
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert first.json() == {
        "event_id": str(event_id),
        "state": "closed",
        "version": 0,
        "event_revision": 0,
    }
    unit.gates[event_id] = GateState(event_id, "open", 4, 7)
    retry = client.put(endpoint(event_id), headers=auth())
    assert retry.status_code == 200
    assert retry.json()["state"] == "open" and retry.json()["version"] == 4
    assert unit.commits == 2


def test_only_put_is_allowed_and_invalid_uuid_does_not_write(isolated):
    client, unit = isolated
    event_id = uuid4()
    assert client.post(endpoint(event_id), headers=auth()).status_code == 405
    assert client.put(endpoint("not-uuid"), headers=auth()).status_code == 422
    assert not unit.gates
