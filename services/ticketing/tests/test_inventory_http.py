"""Public inventory: published Events only, no auth leakage or local sales mutation."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from ticketing_service.inventory_http import (
    InventoryResponse, PublishedEventVerifier, inventory_session, verifier,
)
from ticketing_service.main import app


def remote_verifier(event_id, *, status=200, published=True, other_id=False):
    def handler(request: httpx.Request):
        assert request.url.path == f"/api/v1/events/{event_id}"
        if status != 200:
            return httpx.Response(status)
        now = datetime.now(UTC)
        return httpx.Response(200, json={
            "id": str(uuid4() if other_id else event_id),
            "status": "published" if published else "draft",
            "start_at": (now + timedelta(days=2)).isoformat(),
            "end_at": (now + timedelta(days=3)).isoformat(),
        })

    remote = PublishedEventVerifier(transport=httpx.MockTransport(handler))
    return remote


@pytest.fixture
def client(monkeypatch):
    event_id = uuid4()
    calls = []
    from ticketing_service import inventory_http

    def fake_snapshot(db, incoming_id):
        calls.append(incoming_id)
        return InventoryResponse(event_id=incoming_id, zones=[])

    monkeypatch.setattr(inventory_http, "inventory_snapshot", fake_snapshot)
    app.dependency_overrides[inventory_session] = lambda: None
    app.dependency_overrides[verifier] = lambda: remote_verifier(event_id)
    try:
        with TestClient(app) as http:
            yield http, event_id, calls
    finally:
        app.dependency_overrides.clear()


def test_published_event_returns_frontend_inventory_contract(client):
    http, event_id, calls = client
    result = http.get(f"/api/v1/events/{event_id}/inventory")
    assert result.status_code == 200, result.text
    assert result.json() == {"event_id": str(event_id), "zones": []}
    assert result.headers["cache-control"] == "no-store"
    assert calls == [event_id]


@pytest.mark.parametrize(("status", "published", "other_id", "expected"), [
    (404, True, False, 404),
    (503, True, False, 503),
    (200, False, False, 404),
    (200, True, True, 404),
])
def test_public_inventory_fails_closed_before_reading_database(
    client, status, published, other_id, expected,
):
    http, event_id, calls = client
    app.dependency_overrides[verifier] = lambda: remote_verifier(
        event_id, status=status, published=published, other_id=other_id,
    )
    result = http.get(f"/api/v1/events/{event_id}/inventory")
    assert result.status_code == expected, result.text
    assert not calls


def test_remote_network_failure_is_503(client):
    http, event_id, calls = client

    def failure(request):
        raise httpx.ConnectError("offline", request=request)

    app.dependency_overrides[verifier] = lambda: PublishedEventVerifier(
        transport=httpx.MockTransport(failure),
    )
    response = http.get(f"/api/v1/events/{event_id}/inventory")
    assert response.status_code == 503
    assert calls == []


def test_bad_event_id_returns_422_without_inventory_read(client):
    http, _, calls = client
    response = http.get("/api/v1/events/not-a-uuid/inventory")
    assert response.status_code == 422
    assert not calls
