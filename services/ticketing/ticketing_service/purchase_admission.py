"""Read-only remote Identity and Events checks for Ticketing purchase admission.

No cross-service SQL access and no trust in a buyer-provided customer UUID.
The actual purchase transaction lives in Ticketing's own database.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError


class PurchaseAdmissionUnavailable(Exception):
    """A remote authority could not safely confirm admission."""


class PurchaseAdmissionDenied(Exception):
    """Identity denied the bearer or its role is not a customer."""


@dataclass(frozen=True)
class VerifiedCustomer:
    id: UUID


class IdentityData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    username: str
    display_name: str
    role: str


class PublicEventData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    status: str
    start_at: datetime
    end_at: datetime


def valid_service_url(url: str) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or parts.path not in {"", "/"}
    ):
        raise ValueError("Invalid service base URL")
    return url.rstrip("/")


class HttpPurchaseAdmission:
    def __init__(
        self,
        identity_url: str,
        events_url: str,
        identity_internal_token: str,
        *,
        timeout: float = 2.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.identity_url = valid_service_url(identity_url)
        self.events_url = valid_service_url(events_url)
        if len(identity_internal_token) < 32 or not 0 < timeout <= 10:
            raise ValueError("Purchase admission credential or timeout invalid")
        self.identity_internal_token = identity_internal_token
        self.timeout = timeout
        self.transport = transport

    def customer(self, access_token: str, request_id: str | None = None) -> VerifiedCustomer:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Internal-Service-Token": self.identity_internal_token,
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.get(
                    self.identity_url + "/api/v1/internal/auth/introspect",
                    headers=headers,
                )
        except httpx.RequestError as error:
            raise PurchaseAdmissionUnavailable("Identity unavailable") from error
        if response.status_code == 401:
            raise PurchaseAdmissionDenied("Invalid or revoked Identity session")
        if response.status_code != 200:
            raise PurchaseAdmissionUnavailable("Identity could not verify buyer")
        try:
            principal = IdentityData.model_validate(response.json())
        except (ValueError, TypeError, ValidationError) as error:
            raise PurchaseAdmissionUnavailable("Invalid Identity response") from error
        if principal.role != "customer":
            raise PurchaseAdmissionDenied("Customer role required")
        return VerifiedCustomer(principal.id)

    def public_event(self, event_id: UUID, now: datetime) -> None:
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.get(
                    self.events_url + f"/api/v1/events/{event_id}",
                )
        except httpx.RequestError as error:
            raise PurchaseAdmissionUnavailable("Events unavailable") from error
        if response.status_code == 404:
            raise PurchaseAdmissionDenied("Event is not available")
        if response.status_code != 200:
            raise PurchaseAdmissionUnavailable("Events could not confirm sale")
        try:
            event = PublicEventData.model_validate(response.json())
        except (ValueError, TypeError, ValidationError) as error:
            raise PurchaseAdmissionUnavailable("Invalid Events response") from error
        current = now.astimezone(UTC)
        if (
            event.id != event_id
            or event.status != "published"
            or event.start_at.astimezone(UTC) <= current
            or event.end_at.astimezone(UTC) <= event.start_at.astimezone(UTC)
        ):
            raise PurchaseAdmissionDenied("Event is not eligible for new purchases")
