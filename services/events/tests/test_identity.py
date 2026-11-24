"""Identity HTTP contract: no legacy fallback, no redirects, no unknown roles."""
from uuid import uuid4

import httpx
import pytest

from events_service.identity import (
    HttpIdentityAdapter,
    IdentityUnauthorized,
    IdentityUnavailable,
)

TOKEN = "private-test-token-long-enough-for-ci-2026"


def adapter(handler):
    return HttpIdentityAdapter(
        "http://identity:8001", TOKEN, transport=httpx.MockTransport(handler),
    )


def test_remote_identity_owner_is_verified_and_request_id_propagated():
    owner = uuid4()

    def respond(request):
        assert request.headers["authorization"] == "Bearer user-session"
        assert request.headers["x-internal-service-token"] == TOKEN
        assert request.headers["x-request-id"] == "test-request-id"
        return httpx.Response(200, json={
            "id": str(owner), "username": "organizer",
            "display_name": "Organizer", "role": "event_owner",
        })

    principal = adapter(respond).introspect("user-session", "test-request-id")
    assert principal.id == owner and principal.role == "event_owner"


@pytest.mark.parametrize("status,error_type", [
    (401, IdentityUnauthorized),
    (403, IdentityUnavailable),
    (500, IdentityUnavailable),
    (302, IdentityUnavailable),
])
def test_remote_rejection_fails_closed(status, error_type):
    verifier = adapter(lambda request: httpx.Response(status))
    with pytest.raises(error_type):
        verifier.introspect("user-session")


def test_malformed_response_is_denied():
    verifier = adapter(lambda request: httpx.Response(200, json={"role": "event_owner"}))
    with pytest.raises(IdentityUnavailable):
        verifier.introspect("user-session")


def test_unknown_role_is_denied():
    verifier = adapter(lambda request: httpx.Response(200, json={
        "id": str(uuid4()), "username": "organizer",
        "display_name": "Organizer", "role": "superuser",
    }))
    with pytest.raises(IdentityUnavailable):
        verifier.introspect("user-session")


def test_network_failure_is_unavailable():
    def fail(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(IdentityUnavailable):
        adapter(fail).introspect("user-session")


def test_missing_internal_secret_refuses_adapter():
    with pytest.raises(ValueError):
        HttpIdentityAdapter("http://identity:8001", "short")
