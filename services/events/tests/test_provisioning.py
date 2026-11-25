"""Events verified provisioning: no arbitrary UUID and safe HTTP uncertainty."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from events_service.domain import EventRecord
from events_service.gate_readiness import GateReadinessDenied
from events_service.provision_http import HttpClosedGateProvisioner
from events_service.provisioning import provision_verified_draft
from events_service.sales_port import SaleGateState, SaleGateUnavailable

NOW = datetime.now(UTC)
OWNER = uuid4()
EVENT = EventRecord(
    id=uuid4(), owner_id=OWNER, name="Show", description="", venue="Hall",
    start_at=NOW + timedelta(days=3), end_at=NOW + timedelta(days=3, hours=2),
    status="draft",
)
TOKEN = "test-ticketing-service-token-at-least-32"


class Reader:
    def __init__(self, row):
        self.row = row

    def by_id(self, event_id):
        return self.row if self.row and self.row.id == event_id else None


class Remote:
    def __init__(self):
        self.calls = 0
        self.result = SaleGateState(EVENT.id, "closed", 0, 0)

    def provision(self, event_id, request_id=None):
        self.calls += 1
        return self.result


@pytest.mark.parametrize("event,actor,role", [
    (None, OWNER, "event_owner"),
    (EVENT, uuid4(), "event_owner"),
    (EVENT, OWNER, "customer"),
    (replace(EVENT, status="published"), OWNER, "event_owner"),
    (replace(EVENT, start_at=NOW - timedelta(days=1)), OWNER, "event_owner"),
])
def test_invalid_event_or_actor_never_contacts_ticketing(event, actor, role):
    remote = Remote()
    with pytest.raises(GateReadinessDenied):
        provision_verified_draft(
            Reader(event), remote, EVENT.id, actor, role, NOW,
        )
    assert remote.calls == 0


def test_verified_owner_contacts_ticketing_only_once():
    remote = Remote()
    outcome = provision_verified_draft(
        Reader(EVENT), remote, EVENT.id, OWNER, "event_owner", NOW, "trace",
    )
    assert outcome.state.state == "closed" and remote.calls == 1


def test_existing_open_gate_is_reported_not_reset():
    remote = Remote()
    remote.result = SaleGateState(EVENT.id, "open", 5, 7)
    outcome = provision_verified_draft(
        Reader(EVENT), remote, EVENT.id, OWNER, "event_owner", NOW,
    )
    assert (outcome.state.state, outcome.state.version) == ("open", 5)


def test_remote_wrong_uuid_is_unconfirmed():
    remote = Remote()
    remote.result = SaleGateState(uuid4(), "closed", 0, 0)
    with pytest.raises(SaleGateUnavailable):
        provision_verified_draft(
            Reader(EVENT), remote, EVENT.id, OWNER, "event_owner", NOW,
        )


def test_http_put_credentials_trace_and_closed_reply():
    def handler(request):
        assert request.method == "PUT"
        assert request.url.path.endswith(f"/gates/{EVENT.id}/provision")
        assert request.headers["x-internal-service-token"] == TOKEN
        assert request.headers["x-request-id"] == "trace"
        return httpx.Response(200, json={
            "event_id": str(EVENT.id), "state": "closed",
            "version": 0, "event_revision": 0,
        })
    client = HttpClosedGateProvisioner(
        "http://ticketing:8003", TOKEN, transport=httpx.MockTransport(handler),
    )
    assert client.provision(EVENT.id, "trace").state == "closed"


@pytest.mark.parametrize("status", [401, 403, 404, 409, 500, 302])
def test_http_failures_are_unconfirmed(status):
    adapter = HttpClosedGateProvisioner(
        "http://ticketing:8003", TOKEN,
        transport=httpx.MockTransport(lambda req: httpx.Response(status)),
    )
    with pytest.raises(SaleGateUnavailable):
        adapter.provision(EVENT.id)


def test_timeout_after_possible_commit_does_not_assume_success():
    def handler(request):
        raise httpx.ReadTimeout("lost reply", request=request)
    adapter = HttpClosedGateProvisioner(
        "http://ticketing:8003", TOKEN, transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SaleGateUnavailable):
        adapter.provision(EVENT.id)


def test_invalid_body_and_wrong_event_denied():
    adapter = HttpClosedGateProvisioner(
        "http://ticketing:8003", TOKEN,
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
            "event_id": str(uuid4()), "state": "closed",
            "version": 0, "event_revision": 0,
        })),
    )
    with pytest.raises(SaleGateUnavailable):
        adapter.provision(EVENT.id)
