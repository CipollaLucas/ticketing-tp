"""HTTP adapter for Identity's private introspection API.

No local User table access. A 401 is unauthenticated; a 403 or upstream
failure is unavailable/fail-closed, never a permission grant.
"""
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.ticketing_core.application.identity import (
    AuthenticatedPrincipal,
    IdentityUnauthorized,
    IdentityUnavailable,
)


class IntrospectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    username: str
    display_name: str
    role: str


class HttpIdentityAdapter:
    def __init__(
        self, base_url: str, service_token: str,
        *, timeout_seconds: float = 2.0, transport: httpx.BaseTransport | None = None,
    ):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Identity URL must be absolute HTTP(S)")
        if len(service_token) < 32:
            raise ValueError("Identity internal service credential is required")
        if not 0 < timeout_seconds <= 10:
            raise ValueError("Identity timeout must be between 0 and 10 seconds")
        self.url = base_url.rstrip("/") + "/api/v1/internal/auth/introspect"
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def introspect(
        self, bearer_token: str, request_id: str | None = None,
    ) -> AuthenticatedPrincipal:
        if not bearer_token:
            raise IdentityUnauthorized("Missing Bearer token")
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "X-Internal-Service-Token": self.service_token,
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            with httpx.Client(
                timeout=self.timeout_seconds, transport=self.transport, trust_env=False,
                follow_redirects=False,
            ) as client:
                response = client.get(self.url, headers=headers)
        except httpx.RequestError as error:
            raise IdentityUnavailable("Identity service is unavailable") from error
        if response.status_code == 401:
            raise IdentityUnauthorized("Invalid or expired credentials")
        if response.status_code != 200:
            raise IdentityUnavailable("Identity verification failed")
        try:
            record = IntrospectionResponse.model_validate(response.json())
        except (ValidationError, ValueError) as error:
            raise IdentityUnavailable("Invalid Identity response") from error
        if record.role not in ("customer", "event_owner", "administrator"):
            raise IdentityUnavailable("Unknown Identity role")
        return AuthenticatedPrincipal(
            id=record.id, username=record.username,
            display_name=record.display_name, role=record.role,
        )
