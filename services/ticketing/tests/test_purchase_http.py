"""Purchase HTTP is disabled by default and requires verified customer identity."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ticketing_service.main import app
from ticketing_service.purchase_admission import (
    PurchaseAdmissionDenied,
    PurchaseAdmissionUnavailable,
    VerifiedCustomer,
)
from ticketing_service.purchase_application import (
    OrderRecord,
    PurchaseOutcome,
    TicketRecord,
)
from ticketing_service.purchase_http import admission_port, session_scope
from ticketing_service.settings import settings


class AdmissionStub:
    def __init__(self):
        self.customer_id = uuid4()
        self.identity_error = None
        self.events_error = None
        self.calls = []

    def customer(self, access_token, request_id=None):
        self.calls.append(("identity", access_token))
        if self.identity_error is not None:
            raise self.identity_error
        return VerifiedCustomer(self.customer_id)

    def public_event(self, event_id, now):
        self.calls.append(("events", event_id))
        if self.events_error is not None:
            raise self.events_error


@pytest.fixture
def scenario(monkeypatch):
    customer = AdmissionStub()
    calls = []
    event_id, zone_id = uuid4(), uuid4()
    order_id = uuid4()

    def fake_purchase(intent, customer_id, key, unit):
        calls.append((intent, customer_id, key))
        return PurchaseOutcome(
            OrderRecord(
                id=order_id,
                customer_id=customer_id,
                event_id=event_id,
                status="confirmed",
                total_minor=1000,
                currency="ARS",
                created_at=datetime.now(UTC),
                items=(),
                tickets=(TicketRecord(uuid4(), uuid4(), zone_id, None, "valid"),),
            ),
            replayed=len(calls) > 1,
        )

    monkeypatch.setattr("ticketing_service.purchase_http.purchase_tickets", fake_purchase)
    monkeypatch.setattr(
        "ticketing_service.purchase_http.replay_confirmed_purchase",
        lambda intent, customer_id, key, unit: None,
    )
    app.dependency_overrides[admission_port] = lambda: customer
    app.dependency_overrides[session_scope] = lambda: None
    monkeypatch.setattr(settings, "purchases_enabled", True)
    try:
        with TestClient(app) as client:
            yield client, customer, calls, event_id, zone_id
    finally:
        app.dependency_overrides.clear()


def url(event_id):
    return f"/api/v1/events/{event_id}/orders"


def headers(key="test-key"):
    return {"Authorization": "Bearer valid-token", "Idempotency-Key": key}


def payload(zone_id):
    return {"items": [{"zone_id": str(zone_id), "quantity": 1}]}


def test_opt_in_purchase_contract_and_idempotent_replay(scenario):
    client, admission, calls, event_id, zone_id = scenario
    first = client.post(url(event_id), json=payload(zone_id), headers=headers())
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "confirmed"
    assert first.json()["replayed"] is False
    assert len(first.json()["tickets"]) == 1
    assert first.headers["cache-control"] == "no-store"
    second = client.post(url(event_id), json=payload(zone_id), headers=headers())
    assert second.status_code == 200, second.text
    assert second.json()["replayed"] is True
    assert second.json()["id"] == first.json()["id"]
    assert len(calls) == 2
    assert all(call[1] == admission.customer_id for call in calls)


def test_default_off_and_missing_bearer_fail_without_admission(scenario, monkeypatch):
    client, admission, calls, event_id, zone_id = scenario
    monkeypatch.setattr(settings, "purchases_enabled", False)
    assert client.post(url(event_id), headers=headers(), json=payload(zone_id)).status_code == 404
    monkeypatch.setattr(settings, "purchases_enabled", True)
    assert (
        client.post(
            url(event_id), headers={"Idempotency-Key": "x"}, json=payload(zone_id)
        ).status_code
        == 401
    )
    assert not admission.calls and not calls


def test_invalid_identity_and_unavailable_authorities_fail_closed(scenario):
    client, admission, calls, event_id, zone_id = scenario
    admission.identity_error = PurchaseAdmissionDenied("Not a customer")
    assert client.post(url(event_id), headers=headers(), json=payload(zone_id)).status_code == 403
    admission.identity_error = PurchaseAdmissionUnavailable("Identity offline")
    assert client.post(url(event_id), headers=headers(), json=payload(zone_id)).status_code == 503
    admission.identity_error = None
    admission.events_error = PurchaseAdmissionDenied("Event hidden")
    assert client.post(url(event_id), headers=headers(), json=payload(zone_id)).status_code == 403
    admission.events_error = PurchaseAdmissionUnavailable("Events offline")
    assert client.post(url(event_id), headers=headers(), json=payload(zone_id)).status_code == 503
    assert not calls


@pytest.mark.parametrize(
    "body",
    [
        {"items": []},
        {"items": [{"zone_id": str(uuid4()), "quantity": 0}]},
        {"items": [{"zone_id": str(uuid4()), "quantity": 1, "extra": "forged"}]},
        {"items": [{"zone_id": str(uuid4()), "quantity": 1}], "customer_id": str(uuid4())},
    ],
)
def test_invalid_payload_never_creates_order(scenario, body):
    client, admission, calls, event_id, _ = scenario
    response = client.post(url(event_id), json=body, headers=headers())
    assert response.status_code == 422
    assert not calls and not admission.calls


def test_missing_or_invalid_idempotency_key(scenario):
    client, admission, calls, event_id, zone_id = scenario
    response = client.post(
        url(event_id),
        json=payload(zone_id),
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 422
    response = client.post(url(event_id), json=payload(zone_id), headers=headers("bad key"))
    assert response.status_code == 422
    assert not calls and not admission.calls


def test_historical_replay_does_not_depend_on_events_but_requires_identity(scenario, monkeypatch):
    client, admission, calls, event_id, zone_id = scenario
    from ticketing_service.purchase_application import OrderRecord, PurchaseOutcome

    existing = PurchaseOutcome(
        OrderRecord(
            id=uuid4(),
            customer_id=admission.customer_id,
            event_id=event_id,
            status="confirmed",
            total_minor=1000,
            currency="ARS",
            created_at=datetime.now(UTC),
            items=(),
            tickets=(),
        ),
        replayed=True,
    )
    monkeypatch.setattr(
        "ticketing_service.purchase_http.replay_confirmed_purchase",
        lambda intent, customer_id, key, unit: existing,
    )
    admission.events_error = PurchaseAdmissionUnavailable("Events unreachable")
    result = client.post(url(event_id), headers=headers(), json=payload(zone_id))
    assert result.status_code == 200, result.text
    assert result.json()["id"] == str(existing.order.id)
    assert result.json()["replayed"] is True
    assert admission.calls == [("identity", "valid-token")]
    assert not calls

    admission.calls.clear()
    admission.identity_error = PurchaseAdmissionDenied("Revoked")
    rejected = client.post(url(event_id), headers=headers(), json=payload(zone_id))
    assert rejected.status_code == 403
    assert not calls
    assert admission.calls == [("identity", "valid-token")]
