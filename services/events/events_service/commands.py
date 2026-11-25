"""Protected preview HTTP adapter; no direct user IDs accepted from clients."""
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from events_service.application import owned_events
from events_service.drafts import DraftInput, create_draft
from events_service.edit_draft import EditEventError, EventPatch, edit_draft
from events_service.gate_readiness import GateReadinessDenied, verify_gate_candidate
from events_service.identity import (
    HttpIdentityAdapter,
    IdentityPort,
    IdentityUnauthorized,
    IdentityUnavailable,
)
from events_service.persistence import (
    SqlAlchemyDraftEditPort,
    SqlAlchemyDraftWriter,
    SqlAlchemyEventReader,
    SqlAlchemyPublicationUnitOfWork,
)
from events_service.provision_http import HttpClosedGateProvisioner
from events_service.provisioning import ClosedGateProvisionPort, provision_verified_draft
from events_service.publish_coordinator import publish_via_ticketing
from events_service.publication import PublicationRejected
from events_service.sales_http import HttpTicketingGateAdapter
from events_service.sales_port import SaleGatePort, SaleGateRejected, SaleGateUnavailable
from events_service.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Events protected preview"])
bearer = HTTPBearer(auto_error=False)
NO_STORE = {"Cache-Control": "no-store"}


class CreateEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=5000)
    venue: str = Field(min_length=1, max_length=300)
    start_at: AwareDatetime
    end_at: AwareDatetime


class EventPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    venue: str | None = Field(default=None, min_length=1, max_length=300)
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None


def identity_port() -> IdentityPort:
    if not settings.protected_drafts_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if not settings.identity_service_url or not settings.identity_internal_token:
        raise HTTPException(503, "Identity integration unavailable", headers=NO_STORE)
    try:
        return HttpIdentityAdapter(
            settings.identity_service_url, settings.identity_internal_token,
            timeout=settings.identity_timeout_seconds,
        )
    except ValueError as error:
        raise HTTPException(503, "Identity integration unavailable", headers=NO_STORE) from error


def session_scope():
    # Kept in main; import lazily to avoid a circular import of FastAPI.
    from events_service.main import session_scope as main_session_scope
    yield from main_session_scope()


@router.post("/events", status_code=201)
def create_event(
    payload: CreateEventRequest,
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[IdentityPort, Depends(identity_port)],
    db: Annotated[Session, Depends(session_scope)],
):
    response.headers["Cache-Control"] = "no-store"
    if not settings.protected_drafts_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verifier.introspect(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        ) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable", headers=NO_STORE) from error
    if principal.role not in {"event_owner", "administrator"}:
        raise HTTPException(403, "Event owner role required", headers=NO_STORE)

    try:
        event = create_draft(
            DraftInput(**payload.model_dump()), principal.id,
            SqlAlchemyDraftWriter(db), datetime.now(UTC),
        )
    except ValueError as error:
        raise HTTPException(422, str(error), headers=NO_STORE) from error
    return {
        "id": event.id,
        "owner_id": event.owner_id,
        "name": event.name,
        "description": event.description,
        "venue": event.venue,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "status": event.status,
        "created_at": event.created_at, "updated_at": event.updated_at,
    }


@router.get("/owner/events")
def owner_events(
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[IdentityPort, Depends(identity_port)],
    db: Annotated[Session, Depends(session_scope)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List drafts and published events belonging to the verified organizer.

    Administrators can view all owners; callers cannot inject an owner UUID.
    This endpoint remains unavailable outside the opt-in H3 preview.
    """
    response.headers["Cache-Control"] = "no-store"
    if not settings.protected_drafts_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verifier.introspect(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        ) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable", headers=NO_STORE) from error
    if principal.role not in {"event_owner", "administrator"}:
        raise HTTPException(403, "Event owner role required", headers=NO_STORE)
    owner_id = None if principal.role == "administrator" else principal.id
    rows, total = owned_events(SqlAlchemyEventReader(db), owner_id, limit, offset)
    return {
        "items": [
            {
                "id": row.id, "owner_id": row.owner_id, "name": row.name,
                "description": row.description, "venue": row.venue,
                "start_at": row.start_at, "end_at": row.end_at, "status": row.status,
                "created_at": row.created_at, "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/owner/events/{event_id}/sale-gate-readiness")
def sale_gate_readiness(
    event_id: UUID,
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[IdentityPort, Depends(identity_port)],
    db: Annotated[Session, Depends(session_scope)],
):
    """Authorization preflight only: never provisions or opens a sale gate."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.protected_drafts_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verifier.introspect(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable", headers=NO_STORE) from error
    try:
        candidate = verify_gate_candidate(
            SqlAlchemyEventReader(db), event_id, principal.id, principal.role,
            datetime.now(UTC),
        )
    except GateReadinessDenied as error:
        raise HTTPException(404, "Event unavailable for sale-gate preparation",
                            headers=NO_STORE) from error
    return {
        "event_id": candidate.event_id,
        "status": candidate.status,
        "ready_for_gate_provisioning": True,
        "gate_provisioned": False,
    }


def gate_provision_port() -> ClosedGateProvisionPort:
    """A separate feature flag prevents accidentally enabling sale commands."""
    if not settings.gate_provisioning_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    try:
        return HttpClosedGateProvisioner(
            settings.ticketing_service_url, settings.ticketing_internal_token,
            timeout=settings.ticketing_timeout_seconds,
        )
    except ValueError as error:
        raise HTTPException(503, "Ticketing provisioning unavailable", headers=NO_STORE) from error


@router.put("/owner/events/{event_id}/sale-gate-provision")
def provision_event_gate(
    event_id: UUID,
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[IdentityPort, Depends(identity_port)],
    remote: Annotated[ClosedGateProvisionPort, Depends(gate_provision_port)],
    db: Annotated[Session, Depends(session_scope)],
):
    """Verified committed future draft only; never publish or open sales."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.gate_provisioning_enabled or not settings.protected_drafts_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verifier.introspect(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable", headers=NO_STORE) from error
    try:
        result = provision_verified_draft(
            SqlAlchemyEventReader(db), remote, event_id, principal.id,
            principal.role, datetime.now(UTC), request.headers.get("X-Request-ID"),
        )
    except GateReadinessDenied as error:
        raise HTTPException(404, "Event not available", headers=NO_STORE) from error
    except SaleGateUnavailable as error:
        raise HTTPException(
            503, "Ticketing provisioning unconfirmed; retry with same event ID",
            headers=NO_STORE,
        ) from error
    return {
        "event_id": result.event_id,
        "state": result.state.state,
        "version": result.state.version,
        "event_revision": result.state.event_revision,
    }


@router.patch("/events/{event_id}")
def update_event(
    event_id: UUID,
    payload: EventPatchRequest,
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[IdentityPort, Depends(identity_port)],
    db: Annotated[Session, Depends(session_scope)],
):
    """Stage I draft-only metadata edit; no Ticketing provisioning or publish."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.protected_drafts_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verifier.introspect(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable", headers=NO_STORE) from error
    if principal.role not in {"event_owner", "administrator"}:
        raise HTTPException(403, "Event owner role required", headers=NO_STORE)
    try:
        event = edit_draft(
            event_id, principal.id, principal.role,
            EventPatch(payload.model_dump(exclude_unset=True)),
            SqlAlchemyDraftEditPort(db), datetime.now(UTC),
        )
    except EditEventError as error:
        raise HTTPException(error.status, error.detail, headers=NO_STORE) from error
    return {
        "id": event.id, "owner_id": event.owner_id,
        "name": event.name, "description": event.description, "venue": event.venue,
        "start_at": event.start_at, "end_at": event.end_at, "status": event.status,
        "created_at": event.created_at, "updated_at": event.updated_at,
    }


def publication_ports() -> tuple[ClosedGateProvisionPort, SaleGatePort]:
    """Not reachable without a separate opt-in; private credentials only."""
    if not settings.publication_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    try:
        return (
            HttpClosedGateProvisioner(
                settings.ticketing_service_url, settings.ticketing_internal_token,
                timeout=settings.ticketing_timeout_seconds,
            ),
            HttpTicketingGateAdapter(
                settings.ticketing_service_url, settings.ticketing_internal_token,
                timeout=settings.ticketing_timeout_seconds,
            ),
        )
    except ValueError as error:
        raise HTTPException(503, "Ticketing publication unavailable", headers=NO_STORE) from error


@router.post("/events/{event_id}/publish")
def publish_event(
    event_id: UUID,
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    verifier: Annotated[IdentityPort, Depends(identity_port)],
    remotes: Annotated[
        tuple[ClosedGateProvisionPort, SaleGatePort], Depends(publication_ports),
    ],
    db: Annotated[Session, Depends(session_scope)],
):
    """Stage I shape with durable multi-service recovery; OFF by default."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.protected_drafts_enabled or not settings.publication_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={**NO_STORE, "WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verifier.introspect(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable", headers=NO_STORE) from error
    try:
        publish_via_ticketing(
            SqlAlchemyPublicationUnitOfWork(db), remotes[0], remotes[1],
            event_id, principal.id, principal.role,
            datetime.now(UTC), request.headers.get("X-Request-ID"),
        )
    except PublicationRejected as error:
        raise HTTPException(error.status, error.detail, headers=NO_STORE) from error
    except SaleGateRejected as error:
        raise HTTPException(409, "Ticketing sale gate conflict", headers=NO_STORE) from error
    except SaleGateUnavailable as error:
        raise HTTPException(
            503, "Publication not confirmed; retry same event ID",
            headers=NO_STORE,
        ) from error
    event = SqlAlchemyEventReader(db).by_id(event_id)
    assert event is not None and event.status == "published"
    return {
        "id": event.id, "owner_id": event.owner_id,
        "name": event.name, "description": event.description, "venue": event.venue,
        "start_at": event.start_at, "end_at": event.end_at,
        "status": event.status, "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
