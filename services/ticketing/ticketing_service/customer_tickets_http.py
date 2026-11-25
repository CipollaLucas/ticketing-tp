"""Customer-owned ticket queries in Ticketing's independent database.

A verified Identity principal is required; no user UUID is accepted from callers.
Reads do not depend on Events publication or sale-gate status, so historical
tickets remain accessible after an event is closed.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing_service.persistence import OrderItemRow, OrderRow, TicketRow
from ticketing_service.purchase_admission import (
    HttpPurchaseAdmission,
    PurchaseAdmissionDenied,
    PurchaseAdmissionUnavailable,
)
from ticketing_service.purchase_http import session_scope
from ticketing_service.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Customer tickets"])
bearer = HTTPBearer(auto_error=False)
NO_STORE = {"Cache-Control": "no-store"}


class CustomerTicketResponse(BaseModel):
    id: UUID
    order_item_id: UUID
    zone_id: UUID
    seat_id: UUID | None
    status: str


class CustomerTicketPage(BaseModel):
    items: list[CustomerTicketResponse]
    total: int
    limit: int
    offset: int


def ticket_reader_admission() -> HttpPurchaseAdmission:
    try:
        return HttpPurchaseAdmission(
            settings.identity_service_url,
            settings.events_service_url,
            settings.identity_internal_token,
            timeout=settings.purchase_timeout_seconds,
        )
    except ValueError as error:
        raise HTTPException(503, "Identity integration unavailable", headers=NO_STORE) from error


def query_customer_tickets(
    db: Session,
    customer_id: UUID,
    limit: int,
    offset: int,
) -> CustomerTicketPage:
    owned = (
        select(TicketRow)
        .join(OrderItemRow, TicketRow.order_item_id == OrderItemRow.id)
        .join(OrderRow, OrderItemRow.order_id == OrderRow.id)
        .where(OrderRow.customer_id == customer_id)
    )
    total = db.scalar(
        select(func.count(TicketRow.id))
        .join(OrderItemRow, TicketRow.order_item_id == OrderItemRow.id)
        .join(OrderRow, OrderItemRow.order_id == OrderRow.id)
        .where(OrderRow.customer_id == customer_id)
    )
    tickets = db.scalars(
        owned.order_by(OrderRow.created_at.desc(), TicketRow.id).limit(limit).offset(offset)
    ).all()
    return CustomerTicketPage(
        items=[
            CustomerTicketResponse(
                id=t.id,
                order_item_id=t.order_item_id,
                zone_id=t.zone_id,
                seat_id=t.seat_id,
                status=t.status,
            )
            for t in tickets
        ],
        total=total if total is not None else 0,
        limit=limit,
        offset=offset,
    )


@router.get("/me/tickets", response_model=CustomerTicketPage)
def my_tickets(
    request: Request,
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    admission: Annotated[HttpPurchaseAdmission, Depends(ticket_reader_admission)],
    db: Annotated[Session, Depends(session_scope)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CustomerTicketPage:
    response.headers["Cache-Control"] = "no-store"
    if credentials is None:
        raise HTTPException(401, "Invalid or expired credentials", headers=NO_STORE)
    try:
        customer = admission.customer(
            credentials.credentials,
            request.headers.get("X-Request-ID"),
        )
    except PurchaseAdmissionDenied as error:
        raise HTTPException(403, str(error), headers=NO_STORE) from error
    except PurchaseAdmissionUnavailable as error:
        raise HTTPException(503, str(error), headers=NO_STORE) from error
    return query_customer_tickets(db, customer.id, limit, offset)
