"""Executable safety evidence: introspection cannot atomically fence remote writes.

These are specification tests, NOT evidence that remote authorization cutover is safe.
They characterize the race to guide an explicit architecture decision.
"""
from uuid import UUID

import pytest

from app.ticketing_core.application.identity import (
    AuthenticatedPrincipal,
    IdentityUnavailable,
)
from app.ticketing_core.application.remote_authorization import (
    IdentityRoleDenied,
    identity_snapshot,
    verify_remote_authorization,
)

ACCOUNT = UUID("00000000-0000-0000-0000-000000000056")
TOKEN = "proof-only-remote-token"


class MutableRemoteIdentity:
    def __init__(self):
        self.role = "customer"
        self.available = True
        self.requests = 0

    def introspect(self, token, request_id=None):
        assert token == TOKEN
        self.requests += 1
        if not self.available:
            raise IdentityUnavailable("Network outage")
        return AuthenticatedPrincipal(ACCOUNT, "buyer", "Buyer", self.role)


def test_revoke_between_first_and_second_check_denies():
    identity = MutableRemoteIdentity()
    initial = verify_remote_authorization(
        TOKEN, identity, allowed_roles=frozenset({"customer"}),
    )
    identity.role = "event_owner"
    with pytest.raises(IdentityRoleDenied):
        verify_remote_authorization(
            TOKEN, identity, allowed_roles=frozenset({"customer"}),
            expected=identity_snapshot(initial),
        )
    assert identity.requests == 2


def test_unavailable_at_second_check_denies():
    identity = MutableRemoteIdentity()
    initial = verify_remote_authorization(
        TOKEN, identity, allowed_roles=frozenset({"customer"}),
    )
    identity.available = False
    with pytest.raises(IdentityUnavailable):
        verify_remote_authorization(
            TOKEN, identity, allowed_roles=frozenset({"customer"}),
            expected=identity_snapshot(initial),
        )
    assert identity.requests == 2


def test_revoke_after_final_check_exposes_unfenced_commit_window():
    """A green authorization check is NOT a lease or a transaction fence.

    The remote authority can revoke a role immediately after introspection
    returns. Without a shared serialization mechanism, a later local commit
    cannot prove that the role remained valid for the full operation.
    """
    identity = MutableRemoteIdentity()
    initial = verify_remote_authorization(
        TOKEN, identity, allowed_roles=frozenset({"customer"}),
    )
    final = verify_remote_authorization(
        TOKEN, identity, allowed_roles=frozenset({"customer"}),
        expected=identity_snapshot(initial),
    )
    # Concurrent administrator change after the final HTTP response.
    identity.role = "event_owner"

    # This observation is the vulnerability that the next architecture
    # increment must address; it is intentionally not a successful checkout.
    assert final.role == "customer"
    assert identity.role != final.role
    assert identity.requests == 2
