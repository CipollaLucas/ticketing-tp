"""Remote authorization decisions cannot be cached across a transaction."""
from uuid import UUID

import pytest

from app.ticketing_core.application.identity import (
    AuthenticatedPrincipal,
    IdentityUnauthorized,
    IdentityUnavailable,
)
from app.ticketing_core.application.remote_authorization import (
    IdentityDrift,
    IdentityRoleDenied,
    identity_snapshot,
    verify_remote_authorization,
)

ID = UUID("00000000-0000-0000-0000-000000000042")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000043")
TOKEN = "remote-test-token"


class ChangingIdentity:
    def __init__(self, *results):
        self.results = iter(results)
        self.calls = 0

    def introspect(self, token, request_id=None):
        assert token == TOKEN
        self.calls += 1
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


def principal(role="customer", *, id=ID, username="buyer"):
    return AuthenticatedPrincipal(id, username, "Buyer", role)


def test_role_is_rechecked_after_lock_instead_of_using_initial_grant():
    remote = ChangingIdentity(principal(), principal("event_owner"))
    initial = verify_remote_authorization(
        TOKEN, remote, allowed_roles=frozenset({"customer"}),
    )
    with pytest.raises(IdentityRoleDenied):
        verify_remote_authorization(
            TOKEN, remote, allowed_roles=frozenset({"customer"}),
            expected=identity_snapshot(initial),
        )
    assert remote.calls == 2


@pytest.mark.parametrize("second", [
    IdentityUnauthorized("revoked"),
    IdentityUnavailable("timeout"),
    principal(id=OTHER_ID),
    principal(username="different"),
])
def test_second_verification_fails_closed(second):
    remote = ChangingIdentity(principal(), second)
    first = verify_remote_authorization(
        TOKEN, remote, allowed_roles=frozenset({"customer"}),
    )
    with pytest.raises((IdentityUnauthorized, IdentityUnavailable, IdentityDrift)):
        verify_remote_authorization(
            TOKEN, remote, allowed_roles=frozenset({"customer"}),
            expected=identity_snapshot(first),
        )
    assert remote.calls == 2


def test_same_identity_and_current_role_allow_second_verification():
    remote = ChangingIdentity(principal(), principal())
    first = verify_remote_authorization(
        TOKEN, remote, allowed_roles=frozenset({"customer"}),
    )
    second = verify_remote_authorization(
        TOKEN, remote, allowed_roles=frozenset({"customer"}),
        expected=identity_snapshot(first),
    )
    assert second.id == first.id
    assert remote.calls == 2


@pytest.mark.parametrize("roles", [
    frozenset(), frozenset({"made_up"}), frozenset({"customer", "superuser"}),
])
def test_invalid_role_configuration_is_rejected_before_remote_call(roles):
    remote = ChangingIdentity(principal())
    with pytest.raises(ValueError):
        verify_remote_authorization(TOKEN, remote, allowed_roles=roles)
    assert remote.calls == 0
