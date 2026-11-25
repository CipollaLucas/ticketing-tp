"""Private, opt-in sale-gate API. Never a public purchase route.

Only the Events service may use the internal credential; event ownership and
actor authorization remain Events/Identity responsibilities.
"""
from hmac import compare_digest
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ticketing_service.application import change_sale_gate
from ticketing_service.domain import GateCommand, GateConflict
from ticketing_service.no_sales_close import ConfirmedSalesExist, close_gate_without_sales
from ticketing_service.persistence import SaleGateRow, SqlAlchemyGateUnitOfWork, engine
from ticketing_service.settings import settings

router = APIRouter(prefix="/api/v1/internal/sales", tags=["Internal sales"])
NO_STORE = {"Cache-Control": "no-store"}


class SaleCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: UUID
    action: Literal["open", "close"]
    expected_version: int = Field(ge=0)
    event_revision: int = Field(ge=0)


class SaleStateResponse(BaseModel):
    event_id: UUID
    state: Literal["open", "closed"]
    version: int
    event_revision: int


def session_scope():
    with Session(engine) as db:
        yield db


def require_events_service(
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    # No HTTP command is reachable by default in production or on a local pull.
    if not settings.sale_commands_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if len(settings.events_internal_token) < 32:
        raise HTTPException(503, "Sales command integration unavailable", headers=NO_STORE)
    if not internal_token or not compare_digest(
        internal_token.encode("utf-8"), settings.events_internal_token.encode("utf-8"),
    ):
        raise HTTPException(401, "Unauthorized internal caller", headers=NO_STORE)


@router.get("/gates/{event_id}", response_model=SaleStateResponse)
def read_sale_gate(
    event_id: UUID,
    response: Response,
    _: Annotated[None, Depends(require_events_service)],
    db: Annotated[Session, Depends(session_scope)],
):
    response.headers["Cache-Control"] = "no-store"
    gate = db.get(SaleGateRow, event_id)
    if gate is None:
        # Unknown IDs are closed by default, including on the internal status endpoint.
        return SaleStateResponse(
            event_id=event_id, state="closed", version=0, event_revision=0,
        )
    return SaleStateResponse(
        event_id=gate.event_id, state=cast(Literal["open", "closed"], gate.state), version=gate.version,
        event_revision=gate.event_revision,
    )


@router.post("/gates/{event_id}/commands", response_model=SaleStateResponse)
def change_gate(
    event_id: UUID,
    response: Response,
    payload: SaleCommandRequest,
    _: Annotated[None, Depends(require_events_service)],
    db: Annotated[Session, Depends(session_scope)],
):
    response.headers["Cache-Control"] = "no-store"
    command = GateCommand(
        command_id=payload.command_id, event_id=event_id, action=payload.action,
        expected_version=payload.expected_version,
        event_revision=payload.event_revision,
    )
    try:
        state = change_sale_gate(command, SqlAlchemyGateUnitOfWork(db))
    except GateConflict as error:
        raise HTTPException(409, str(error), headers=NO_STORE) from error
    return SaleStateResponse(
        event_id=state.event_id, state=state.state, version=state.version,
        event_revision=state.event_revision,
    )


@router.post("/gates/{event_id}/close-without-sales", response_model=SaleStateResponse)
def close_gate_for_unpublish(
    event_id: UUID,
    response: Response,
    payload: SaleCommandRequest,
    _: Annotated[None, Depends(require_events_service)],
    db: Annotated[Session, Depends(session_scope)],
):
    """Only Events can atomically close if there are zero confirmed orders."""
    response.headers["Cache-Control"] = "no-store"
    if payload.action != "close":
        raise HTTPException(422, "No-sales command requires close", headers=NO_STORE)
    command = GateCommand(
        command_id=payload.command_id, event_id=event_id,
        action="close", expected_version=payload.expected_version,
        event_revision=payload.event_revision,
    )
    try:
        result = close_gate_without_sales(command, SqlAlchemyGateUnitOfWork(db))
    except ConfirmedSalesExist as error:
        raise HTTPException(409, str(error), headers=NO_STORE) from error
    except GateConflict as error:
        raise HTTPException(409, str(error), headers=NO_STORE) from error
    return SaleStateResponse(
        event_id=result.event_id, state=result.state,
        version=result.version, event_revision=result.event_revision,
    )
