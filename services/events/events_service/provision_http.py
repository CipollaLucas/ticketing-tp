"""Events-to-Ticketing private PUT with bounded timeout and strict replies."""
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from events_service.sales_port import SaleGateState, SaleGateUnavailable


class ProvisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    state: Literal["closed", "open"]
    version: int
    event_revision: int


class HttpClosedGateProvisioner:
    def __init__(
        self, base_url: str, token: str, *,
        timeout: float = 2.0, transport: httpx.BaseTransport | None = None,
    ):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Invalid Ticketing base URL")
        if len(token) < 32 or not 0 < timeout <= 10:
            raise ValueError("Invalid Ticketing credential or timeout")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.transport = transport

    def provision(self, event_id: UUID, request_id: str | None = None) -> SaleGateState:
        headers = {"X-Internal-Service-Token": self.token}
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            with httpx.Client(
                transport=self.transport, timeout=self.timeout,
                trust_env=False, follow_redirects=False,
            ) as client:
                result = client.put(
                    f"{self.base_url}/api/v1/internal/sales/gates/{event_id}/provision",
                    headers=headers,
                )
        except httpx.RequestError as error:
            raise SaleGateUnavailable("Provisioning result unknown; retry safe PUT") from error
        if result.status_code != 200:
            raise SaleGateUnavailable("Ticketing provisioning not confirmed")
        try:
            data = ProvisionResponse.model_validate(result.json())
        except (ValidationError, ValueError, TypeError) as error:
            raise SaleGateUnavailable("Ticketing response invalid") from error
        if data.event_id != event_id or data.version < 0 or data.event_revision < 0:
            raise SaleGateUnavailable("Ticketing provision returned inconsistent state")
        return SaleGateState(
            data.event_id, data.state, data.version, data.event_revision,
        )
