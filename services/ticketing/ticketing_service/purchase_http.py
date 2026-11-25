"""Customer purchase HTTP is strictly opt-in; gate+stock+orders stay one UoW."""
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ticketing_service.purchase import (
    PurchaseError,
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
)
from ticketing_service.purchase_admission import (
    HttpPurchaseAdmission,
    PurchaseAdmissionDenied,
    PurchaseAdmissionUnavailable,
)
from ticketing_service.purchase_application import (
    purchase_tickets,
    replay_confirmed_purchase,
)
from ticketing_service.purchase_persistence import SqlAlchemyPurchaseUnitOfWork
from ticketing_service.sale_http import session_scope
from ticketing_service.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Purchases"])
bearer = HTTPBearer(auto_error=False)
NO_STORE = {"Cache-Control": "no-store"}


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zone_id: UUID
    quantity: int = Field(ge=1, le=100)
    seat_ids: list[UUID] = Field(default_factory=list, max_length=100)


class PurchaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[SelectionRequest] = Field(min_length=1, max_length=20)


def admission_port() -> HttpPurchaseAdmission:
    if not settings.purchases_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    try:
        return HttpPurchaseAdmission(
            settings.identity_service_url, settings.events_service_url,
            settings.identity_internal_token, timeout=settings.purchase_timeout_seconds,
        )
    except ValueError as error:
        raise HTTPException(503, "Purchase verification unavailable", headers=NO_STORE) from error


@router.post("/events/{event_id}/orders", status_code=201)
def create_order(
    event_id: UUID,
    payload: PurchaseRequest,
    response: Response,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")],
    admission: Annotated[HttpPurchaseAdmission, Depends(admission_port)],
    db: Annotated[Session, Depends(session_scope)],
):
    response.headers["Cache-Control"] = "no-store"
    if not settings.purchases_enabled:
        raise HTTPException(404, "Not found", headers=NO_STORE)
    if credentials is None:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE)
    if idempotency_key is None:
        raise HTTPException(422, "Idempotency-Key required", headers=NO_STORE)
    intent = PurchaseIntent(
        event_id,
        tuple(TicketSelection(item.zone_id, item.quantity, tuple(item.seat_ids))
              for item in payload.items),
    )
    # Validate request before contacting remote authorities or acquiring a DB lock.
    from ticketing_service.purchase import validate_purchase

    try:
        validate_purchase(intent, idempotency_key)
        customer = admission.customer(
            credentials.credentials, request.headers.get("X-Request-ID"),
        )
        # Identity is mandatory even for historical replay; Events is not.
        # Re-check the customer-scoped key in PostgreSQL before authorizing
        # a NEW purchase, so closed gates never cause duplicate allocation.
        outcome = replay_confirmed_purchase(
            intent, customer.id, idempotency_key,
            SqlAlchemyPurchaseUnitOfWork(db),
        )
        if outcome is None:
            admission.public_event(event_id, datetime.now(UTC))
            outcome = purchase_tickets(
                intent, customer.id, idempotency_key,
                SqlAlchemyPurchaseUnitOfWork(db),
            )
    except PurchaseAdmissionDenied as error:
        raise HTTPException(403, str(error), headers=NO_STORE) from error
    except PurchaseAdmissionUnavailable as error:
        raise HTTPException(503, str(error), headers=NO_STORE) from error
    except PurchaseKeyConflict as error:
        raise HTTPException(409, str(error), headers=NO_STORE) from error
    except PurchaseError as error:
        raise HTTPException(error.status, error.detail, headers=NO_STORE) from error
    if outcome.replayed:
        response.status_code = 200
    order = outcome.order
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "event_id": order.event_id,
        "status": order.status,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "created_at": order.created_at,
        "replayed": outcome.replayed,
        "items": [
            {
                "id": item.id, "zone_id": item.zone_id,
                "quantity": item.quantity,
                "unit_price_minor": item.unit_price_minor,
                "subtotal_minor": item.subtotal_minor,
            } for item in order.items
        ],
        "tickets": [
            {
                "id": ticket.id, "order_item_id": ticket.order_item_id,
                "zone_id": ticket.zone_id, "seat_id": ticket.seat_id,
                "status": ticket.status,
            } for ticket in order.tickets
        ],
    }
