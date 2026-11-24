"""Protected preview HTTP adapter; no direct user IDs accepted from clients."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from events_service.drafts import DraftInput, create_draft
from events_service.identity import (
    HttpIdentityAdapter,
    IdentityPort,
    IdentityUnauthorized,
    IdentityUnavailable,
)
from events_service.persistence import SqlAlchemyDraftWriter
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


def identity_port() -> IdentityPort:
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
            SqlAlchemyDraftWriter(db), datetime.now().astimezone(),
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
    }
