"""Contract tests: HTTP adapter uses a private transport and fails closed."""
from uuid import UUID

import httpx
import pytest

from app.ticketing_core.adapters.outbound.http_identity import HttpIdentityAdapter
from app.ticketing_core.application.identity import (
    IdentityUnauthorized,
    IdentityUnavailable,
    authenticate_remote,
)

URL = "http://identity:8001"
SECRET = "only-for-tests-internal-service-secret-12345"
USER = "00000000-0000-0000-0000-000000000001"


def adapter(responder):
    return HttpIdentityAdapter(
        URL, SECRET, transport=httpx.MockTransport(responder), timeout_seconds=0.5,
    )


def test_real_contract_and_header_propagation():
    def responder(request):
        assert request.url.path == "/api/v1/internal/auth/introspect"
        assert request.headers["authorization"] == "Bearer user-token"
        assert request.headers["x-internal-service-token"] == SECRET
        assert request.headers["x-request-id"] == "test-request"
        return httpx.Response(200, json={
            "id": USER, "username": "customer_demo",
            "display_name": "Customer", "role": "customer",
        })

    principal = authenticate_remote("user-token", adapter(responder), "test-request")
    assert principal.id == UUID(USER)
    assert principal.role == "customer"


@pytest.mark.parametrize("status,exception", [
    (401, IdentityUnauthorized),
    (403, IdentityUnavailable),
    (404, IdentityUnavailable),
    (429, IdentityUnavailable),
    (500, IdentityUnavailable),
    (503, IdentityUnavailable),
])
def test_upstream_rejection_never_grants_access(status, exception):
    client = adapter(lambda _: httpx.Response(status, json={"detail": "no"}))
    with pytest.raises(exception):
        authenticate_remote("token", client)


def test_malformed_payload_is_not_trusted():
    for body in (
        {"id": USER, "username": "x", "display_name": "x", "role": "superuser"},
        {"id": USER, "username": "x", "role": "customer"},
        {"id": "not-uuid", "username": "x", "display_name": "x", "role": "customer"},
    ):
        client = adapter(lambda _: httpx.Response(200, json=body))
        with pytest.raises(IdentityUnavailable):
            authenticate_remote("token", client)


def test_network_timeout_rejects_authentication():
    def fail(request):
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(IdentityUnavailable):
        authenticate_remote("token", adapter(fail))


def test_network_disconnect_rejects_authentication():
    def fail(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(IdentityUnavailable):
        authenticate_remote("token", adapter(fail))


def test_empty_token_is_rejected_before_network_call():
    with pytest.raises(IdentityUnauthorized):
        authenticate_remote("", adapter(lambda _: pytest.fail("should not call HTTP")))


def test_missing_secret_rejected_at_construction():
    with pytest.raises(ValueError, match="credential"):
        HttpIdentityAdapter(URL, "short")


def test_redirect_is_not_followed():
    client = adapter(lambda _: httpx.Response(302, headers={"Location": "http://evil.invalid"}))
    with pytest.raises(IdentityUnavailable):
        authenticate_remote("token", client)
