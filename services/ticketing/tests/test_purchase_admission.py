"""Remote purchase admission must fail closed and never trust caller UUIDs."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from ticketing_service.purchase_admission import (
    HttpPurchaseAdmission,
    PurchaseAdmissionDenied,
    PurchaseAdmissionUnavailable,
)

TOKEN = "h4-private-identity-token-at-least-32-chars"
EVENT = uuid4()
CUSTOMER = uuid4()
NOW = datetime.now(UTC)


def admission(handler):
    return HttpPurchaseAdmission(
        "http://identity:8001",
        "http://events:8002",
        TOKEN,
        transport=httpx.MockTransport(handler),
    )


def identity_ok(request):
    return httpx.Response(
        200,
        json={
            "id": str(CUSTOMER),
            "username": "testbuyer",
            "display_name": "Test Buyer",
            "role": "customer",
        },
    )


def event_ok(request):
    return httpx.Response(
        200,
        json={
            "id": str(EVENT),
            "status": "published",
            "start_at": (NOW + timedelta(days=3)).isoformat(),
            "end_at": (NOW + timedelta(days=3, hours=2)).isoformat(),
        },
    )


def test_verified_identity_and_public_future_event():
    requests = []

    def handler(request):
        requests.append(request)
        if "introspect" in str(request.url):
            return identity_ok(request)
        return event_ok(request)

    port = admission(handler)
    assert port.customer("secret-access", "trace").id == CUSTOMER
    port.public_event(EVENT, NOW)
    assert requests[0].headers["X-Internal-Service-Token"] == TOKEN
    assert requests[0].headers["Authorization"] == "Bearer secret-access"
    assert requests[0].headers["X-Request-ID"] == "trace"
    assert requests[1].url.path == f"/api/v1/events/{EVENT}"


@pytest.mark.parametrize(
    "status,exception",
    [
        (401, PurchaseAdmissionDenied),
        (403, PurchaseAdmissionUnavailable),
        (503, PurchaseAdmissionUnavailable),
        (302, PurchaseAdmissionUnavailable),
    ],
)
def test_identity_denials(status, exception):
    port = admission(lambda request: httpx.Response(status))
    with pytest.raises(exception):
        port.customer("token")


def test_non_customer_rejected():
    def handler(request):
        data = identity_ok(request).json() | {"role": "event_owner"}
        return httpx.Response(200, json=data)

    with pytest.raises(PurchaseAdmissionDenied):
        admission(handler).customer("token")


@pytest.mark.parametrize(
    "status,exception",
    [
        (404, PurchaseAdmissionDenied),
        (503, PurchaseAdmissionUnavailable),
        (302, PurchaseAdmissionUnavailable),
    ],
)
def test_public_event_denials(status, exception):
    port = admission(lambda request: httpx.Response(status))
    with pytest.raises(exception):
        port.public_event(EVENT, NOW)


def test_mismatched_or_past_event_rejected():
    for item in [
        event_ok(None).json() | {"id": str(uuid4())},
        event_ok(None).json() | {"status": "draft"},
        event_ok(None).json() | {"start_at": (NOW - timedelta(days=1)).isoformat()},
    ]:
        port = admission(lambda request, item=item: httpx.Response(200, json=item))
        with pytest.raises(PurchaseAdmissionDenied):
            port.public_event(EVENT, NOW)


def test_network_timeout_never_grants_purchase():
    def handler(request):
        raise httpx.ReadTimeout("upstream down")

    port = admission(handler)
    with pytest.raises(PurchaseAdmissionUnavailable):
        port.customer("token")
    with pytest.raises(PurchaseAdmissionUnavailable):
        port.public_event(EVENT, NOW)


@pytest.mark.parametrize(
    "url",
    [
        "http://identity:8001/path",
        "http://user:password@identity:8001",
        "ftp://identity:8001",
        "http://identity:8001/?token=abc",
    ],
)
def test_invalid_base_url_cannot_construct_adapter(url):
    with pytest.raises(ValueError):
        HttpPurchaseAdmission(url, "http://events:8002", TOKEN)
