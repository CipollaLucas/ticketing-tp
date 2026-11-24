"""Identity application port and principal snapshot, independent of transport and ORM."""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    id: UUID
    username: str
    display_name: str
    role: str


class IdentityUnavailable(Exception):
    """Identity cannot be verified: protected work must fail closed."""


class IdentityUnauthorized(Exception):
    """Identity explicitly rejects this Bearer token."""


class IdentityPort(Protocol):
    def introspect(self, bearer_token: str, request_id: str | None = None) -> AuthenticatedPrincipal:
        """Verify the *current* session and role using Identity as source of truth."""
        ...


def authenticate_remote(
    bearer_token: str, port: IdentityPort, request_id: str | None = None,
) -> AuthenticatedPrincipal:
    if not bearer_token:
        raise IdentityUnauthorized("Missing Bearer token")
    return port.introspect(bearer_token, request_id)
