"""Pre-cutover remote authorization gate; no endpoint currently calls this.

Keep remote identity checks out of persistence adapters. Call the gate again
AFTER acquiring resource locks and BEFORE committing business changes.
"""
from dataclasses import dataclass
from uuid import UUID

from app.ticketing_core.application.identity import (
    AuthenticatedPrincipal,
    IdentityPort,
    IdentityUnavailable,
    authenticate_remote,
)


class IdentityDrift(IdentityUnavailable):
    """A token resolves to a different account than the request started with."""


class IdentityRoleDenied(Exception):
    """The remote account exists but does not have the required role."""


@dataclass(frozen=True)
class AuthorizationSnapshot:
    id: UUID
    username: str


def verify_remote_authorization(
    token: str,
    port: IdentityPort,
    *,
    allowed_roles: frozenset[str],
    expected: AuthorizationSnapshot | None = None,
) -> AuthenticatedPrincipal:
    """Read the current remote session and role, without caching or fallback.

    expected is established by the initial verification and reused on later
    checks within the same operation. A role change cannot preserve privilege:
    roles are verified anew on every call.
    """
    if not allowed_roles or not allowed_roles <= {
        "customer", "event_owner", "administrator",
    }:
        raise ValueError("Allowed roles must be a nonempty known subset")
    principal = authenticate_remote(token, port)
    if expected is not None and (
        principal.id != expected.id or principal.username != expected.username
    ):
        raise IdentityDrift("Remote account changed during authorization")
    if principal.role not in allowed_roles:
        raise IdentityRoleDenied("Required remote role is not active")
    return principal


def identity_snapshot(principal: AuthenticatedPrincipal) -> AuthorizationSnapshot:
    return AuthorizationSnapshot(id=principal.id, username=principal.username)
