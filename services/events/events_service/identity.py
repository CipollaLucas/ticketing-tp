"""Identity verification port and fail-closed HTTP adapter for Events.

Identity credentials are never read from the Events database.
"""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class Principal:
    id: UUID
    username: str
    role: str


class IdentityUnauthorized(Exception):
    """Access token rejected by Identity."""


class IdentityUnavailable(Exception):
    """Identity cannot verify the request safely."""


class IdentityPort(Protocol):
    def introspect(self, token: str, request_id: str | None = None) -> Principal: ...


class IdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    username: str
    display_name: str
    role: str


class HttpIdentityAdapter:
    def __init__(
        self, base_url: str, service_token: str, *,
        timeout: float = 2.0, transport: httpx.BaseTransport | None = None,
    ):
        if not base_url.startswith(("http://", "https://")) or "@" in base_url:
            raise ValueError("Valid Identity service URL required")
        if len(service_token) < 32:
            raise ValueError("Internal Identity credential must be at least 32 characters")
        if not 0 < timeout <= 10:
            raise ValueError("Identity timeout must be between zero and ten seconds")
        self.url = base_url.rstrip("/") + "/api/v1/internal/auth/introspect"
        self.service_token = service_token
        self.timeout = timeout
        self.transport = transport

    def introspect(self, token: str, request_id: str | None = None) -> Principal:
        if not token:
            raise IdentityUnauthorized("Missing bearer token")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Internal-Service-Token": self.service_token,
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            with httpx.Client(
                transport=self.transport, timeout=self.timeout,
                trust_env=False, follow_redirects=False,
            ) as client:
                response = client.get(self.url, headers=headers)
        except httpx.RequestError as error:
            raise IdentityUnavailable("Identity is unavailable") from error
        if response.status_code == 401:
            raise IdentityUnauthorized("Invalid or expired session")
        if response.status_code != 200:
            raise IdentityUnavailable("Identity verification could not be completed")
        try:
            result = IdentityResponse.model_validate(response.json())
        except (ValueError, TypeError) as error:
            raise IdentityUnavailable("Identity returned an invalid response") from error
        if result.role not in {"customer", "event_owner", "administrator"}:
            raise IdentityUnavailable("Identity returned an unknown role")
        return Principal(result.id, result.username, result.role)
