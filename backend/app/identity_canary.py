"""Read-only canary for future Identity cutover, disabled by default.

This endpoint is *not* a login endpoint and is never used to authorize
Events, purchases, zones, or administration.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.settings import settings
from app.ticketing_core.adapters.outbound.http_identity import HttpIdentityAdapter
from app.ticketing_core.application.identity import (
    IdentityUnauthorized,
    IdentityUnavailable,
    authenticate_remote,
)

router = APIRouter(prefix="/api/v1", tags=["Identity cutover (preview)"])
bearer = HTTPBearer(auto_error=False)


class CanaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    username: str
    role: str
    identity_verified: bool
    legacy_uuid_role_match: bool


def identity_adapter() -> HttpIdentityAdapter:
    if not settings.identity_service_url or not settings.identity_internal_token:
        raise HTTPException(503, "Identity verification is not configured")
    try:
        return HttpIdentityAdapter(
            settings.identity_service_url, settings.identity_internal_token,
            timeout_seconds=settings.identity_timeout_seconds,
        )
    except ValueError as error:
        raise HTTPException(503, "Identity verification is not configured") from error


@router.get("/identity/canary", response_model=CanaryResponse)
def identity_canary(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> CanaryResponse:
    """No mutation and no fallback to a legacy session on failed introspection."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.identity_canary_enabled:
        raise HTTPException(404, "Not found")
    if credentials is None:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        principal = authenticate_remote(
            credentials.credentials, identity_adapter(),
        )
    except IdentityUnauthorized as error:
        raise HTTPException(
            401, "Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except IdentityUnavailable as error:
        raise HTTPException(503, "Identity verification unavailable") from error

    # Preserve legacy foreign keys and record ownership. This is diagnostic
    # only: it does not confer any right to mutate or purchase.
    legacy = db.get(User, principal.id)
    if legacy is None or (
        legacy.username != principal.username
        or legacy.role != principal.role
    ):
        raise HTTPException(409, "Identity and Legacy accounts are not synchronized")
    return CanaryResponse(
        id=principal.id, username=principal.username,
        role=principal.role, identity_verified=True, legacy_uuid_role_match=True,
    )
