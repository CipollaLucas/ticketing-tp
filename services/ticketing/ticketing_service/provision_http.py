"""Fail-closed private endpoint for Events-verified, committed draft event UUIDs.

Not activated by default. Only an Events service caller (not a browser bearer)
can invoke this route. Events must independently re-check its own durable
event and Identity principal inside the eventual provisioning command.
"""
from hmac import compare_digest
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ticketing_service.domain import GateState
from ticketing_service.persistence import engine
from ticketing_service.provision import GateProvisionUnitOfWork, provision_closed_gate
from ticketing_service.provision_persistence import SqlAlchemyGateProvisionUnitOfWork
from ticketing_service.settings import settings

router = APIRouter(prefix="/api/v1/internal/sales", tags=["Private provision preview"])
NO_STORE = {"Cache-Control": "no-store"}


class ProvisionResponse(BaseModel):
    event_id: UUID
    state: Literal["closed", "open"]
    version: int
    event_revision: int


def require_events_provisioner(
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    if not settings.gate_provisioning_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    secret = settings.events_internal_token
    if len(secret) < 32:
        raise HTTPException(503, "Provisioning integration unavailable", headers=NO_STORE)
    if internal_token is None or not compare_digest(
        internal_token.encode("utf-8"), secret.encode("utf-8"),
    ):
        raise HTTPException(401, "Unauthorized internal caller", headers=NO_STORE)


def provision_unit():
    with Session(engine) as db:
        yield SqlAlchemyGateProvisionUnitOfWork(db)


@router.put("/gates/{event_id}/provision", response_model=ProvisionResponse)
def provision_gate(
    event_id: UUID,
    response: Response,
    _: Annotated[None, Depends(require_events_provisioner)],
    unit: Annotated[GateProvisionUnitOfWork, Depends(provision_unit)],
):
    """Only creates a closed gate; retries do not modify an existing gate."""
    response.headers["Cache-Control"] = "no-store"
    state: GateState = provision_closed_gate(event_id, unit)
    return ProvisionResponse(
        event_id=state.event_id, state=state.state,
        version=state.version, event_revision=state.event_revision,
    )
