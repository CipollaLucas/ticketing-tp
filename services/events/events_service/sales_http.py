"""Fail-closed outbound HTTP adapter for Ticketing's private sale-state API."""
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from events_service.sales_port import (
    SaleGateCommand,
    SaleGateRejected,
    SaleGateState,
    SaleGateUnavailable,
)


class GateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    state: Literal["open", "closed"]
    version: int
    event_revision: int


class HttpTicketingGateAdapter:
    def __init__(
        self, base_url: str, service_token: str, *,
        timeout: float = 2.0, transport: httpx.BaseTransport | None = None,
    ):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError("Valid Ticketing service base URL required")
        if len(service_token) < 32:
            raise ValueError("Internal Ticketing credential must be at least 32 characters")
        if not 0 < timeout <= 10:
            raise ValueError("Ticketing timeout must be between zero and ten seconds")
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout = timeout
        self.transport = transport

    def _request(
        self, method: str, event_id: UUID, payload: dict[str, object] | None,
        request_id: str | None,
        *, conditional_close: bool = False,
    ) -> SaleGateState:
        endpoint = f"/api/v1/internal/sales/gates/{event_id}"
        if method == "POST":
            endpoint += "/close-without-sales" if conditional_close else "/commands"
        headers = {"X-Internal-Service-Token": self.service_token}
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            with httpx.Client(
                transport=self.transport, timeout=self.timeout,
                trust_env=False, follow_redirects=False,
            ) as client:
                response = client.request(
                    method, self.base_url + endpoint, headers=headers, json=payload,
                )
        except httpx.RequestError as error:
            raise SaleGateUnavailable("Ticketing response is unknown") from error
        if response.status_code == 409:
            raise SaleGateRejected("Ticketing reported a gate conflict")
        if response.status_code != 200:
            raise SaleGateUnavailable("Ticketing could not confirm gate state")
        try:
            parsed = GateResponse.model_validate(response.json())
        except (ValidationError, ValueError, TypeError) as error:
            raise SaleGateUnavailable("Ticketing returned an invalid response") from error
        if (
            parsed.event_id != event_id
            or parsed.state not in {"open", "closed"}
            or parsed.version < 0
            or parsed.event_revision < 0
        ):
            raise SaleGateUnavailable("Ticketing returned inconsistent gate state")
        return SaleGateState(
            event_id=parsed.event_id, state=parsed.state,
            version=parsed.version, event_revision=parsed.event_revision,
        )

    def close_without_sales(
        self, value: SaleGateCommand, request_id: str | None = None,
    ) -> SaleGateState:
        if value.action != "close" or value.expected_version < 0 or value.event_revision < 0:
            raise SaleGateRejected("Invalid conditional close command")
        payload: dict[str, object] = {
            "command_id": str(value.command_id),
            "action": "close",
            "expected_version": value.expected_version,
            "event_revision": value.event_revision,
        }
        # A distinct endpoint prevents a generic close command from bypassing
        # the no-confirmed-orders rule for Stage I unpublish.
        result = self._request(
            "POST", value.event_id, payload, request_id,
            conditional_close=True,
        )
        if (
            result.version != value.expected_version + 1
            or result.state != "closed"
            or result.event_revision != value.event_revision
        ):
            raise SaleGateUnavailable("Unconfirmed conditional Ticketing close")
        return result

    def state(self, event_id: UUID, request_id: str | None = None) -> SaleGateState:
        return self._request("GET", event_id, None, request_id)

    def command(
        self, value: SaleGateCommand, request_id: str | None = None,
    ) -> SaleGateState:
        if value.expected_version < 0 or value.event_revision < 0:
            raise SaleGateRejected("Invalid command version")
        payload: dict[str, object] = {
            "command_id": str(value.command_id),
            "action": value.action,
            "expected_version": value.expected_version,
            "event_revision": value.event_revision,
        }
        state = self._request("POST", value.event_id, payload, request_id)
        if state.version != value.expected_version + 1:
            # A replay may return a previously stored result. It must remain
            # consistent with the original command, not a later gate state.
            raise SaleGateUnavailable("Unconfirmed Ticketing command result")
        if state.state != ("open" if value.action == "open" else "closed"):
            raise SaleGateUnavailable("Ticketing returned unexpected action state")
        return state
