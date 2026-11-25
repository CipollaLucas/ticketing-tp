"""Ticketing internal HTTP contract; no Events publication endpoint is activated."""
from uuid import uuid4

import httpx
import pytest

from events_service.sales_http import HttpTicketingGateAdapter
from events_service.sales_port import (
    SaleGateCommand,
    SaleGateRejected,
    SaleGateUnavailable,
    verified_gate_state,
)

SECRET = "h3-h4-service-token-32-characters-for-test"
EVENT = uuid4()


def adapter(handler):
    return HttpTicketingGateAdapter(
        "http://ticketing:8003", SECRET, transport=httpx.MockTransport(handler),
    )


def response(state="closed", version=0, revision=0, event=EVENT):
    return httpx.Response(200, json={
        "event_id": str(event), "state": state,
        "version": version, "event_revision": revision,
    })


def test_private_read_forwards_service_identity_and_request_id():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == f"/api/v1/internal/sales/gates/{EVENT}"
        assert request.headers["x-internal-service-token"] == SECRET
        assert request.headers["x-request-id"] == "h3-trace"
        return response()
    result = verified_gate_state(adapter(handler), EVENT, "h3-trace")
    assert result.state == "closed" and result.version == 0


def test_private_command_has_stable_idempotency_id_and_expected_version():
    command_id = uuid4()
    command = SaleGateCommand(EVENT, command_id, "close", 1, 3)
    def handler(request):
        assert request.method == "POST"
        assert request.url.path.endswith(f"/gates/{EVENT}/commands")
        body = __import__("json").loads(request.content)
        assert body == {
            "command_id": str(command_id), "action": "close",
            "expected_version": 1, "event_revision": 3,
        }
        assert request.headers["x-internal-service-token"] == SECRET
        return response(version=2, revision=3)
    result = adapter(handler).command(command)
    assert result.state == "closed" and result.version == 2


@pytest.mark.parametrize("status,error", [
    (401, SaleGateUnavailable),
    (403, SaleGateUnavailable),
    (404, SaleGateUnavailable),
    (409, SaleGateRejected),
    (500, SaleGateUnavailable),
    (302, SaleGateUnavailable),
])
def test_remote_non_success_fails_closed(status, error):
    with pytest.raises(error):
        adapter(lambda request: httpx.Response(status)).state(EVENT)


@pytest.mark.parametrize("bad", [
    {"event_id": str(EVENT), "state": "open", "version": -1, "event_revision": 0},
    {"event_id": str(uuid4()), "state": "closed", "version": 0, "event_revision": 0},
    {"event_id": str(EVENT), "state": "unknown", "version": 0, "event_revision": 0},
    {"event_id": str(EVENT), "state": "closed", "version": 0},
])
def test_malformed_or_inconsistent_remote_state_fails_closed(bad):
    with pytest.raises(SaleGateUnavailable):
        adapter(lambda request: httpx.Response(200, json=bad)).state(EVENT)


def test_remote_timeout_is_unknown_not_success():
    def unavailable(request):
        raise httpx.ReadTimeout("interrupted after possible commit", request=request)
    with pytest.raises(SaleGateUnavailable):
        adapter(unavailable).command(SaleGateCommand(EVENT, uuid4(), "close", 1, 1))


def test_command_requires_matching_acknowledgement():
    with pytest.raises(SaleGateUnavailable):
        adapter(lambda request: response(state="open", version=2, revision=1)).command(
            SaleGateCommand(EVENT, uuid4(), "close", 1, 1),
        )


@pytest.mark.parametrize("base,secret", [
    ("http://ticketing:8003", "short"),
    ("https://name:pass@ticketing:8003", SECRET),
    ("http://ticketing:8003/api", SECRET),
    ("ftp://ticketing:8003", SECRET),
])
def test_bad_config_never_creates_client(base, secret):
    with pytest.raises(ValueError):
        HttpTicketingGateAdapter(base, secret)
