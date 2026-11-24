"""Atomic simulated purchases; PostgreSQL is the concurrency authority."""
from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, Db, StrictRequest
from app.events import Limit, Offset
from app.models import Role, User
from app.ticketing_core.adapters.outbound.sqlalchemy_queries import SqlAlchemyTicketQueries
from app.ticketing_core.application.queries import (
    get_my_tickets as query_tickets,
    get_order as query_order,
)
from app.ticketing_core.adapters.outbound.sqlalchemy_purchase import (
    SqlAlchemyPurchaseUnitOfWork,
)
from app.ticketing_core.application.ports import PurchaseError
from app.ticketing_core.application.purchase_tickets import purchase_tickets
from app.ticketing_core.domain.purchase import (
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
)

router = APIRouter(prefix="/api/v1", tags=["Purchasing"])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128,
                            pattern=r"^[\x21-\x7e]+$")]


def require_customer(user: CurrentUser) -> User:
    if user.role != Role.CUSTOMER:
        raise HTTPException(403, "Customer role required")
    return user


Customer = Annotated[User, Depends(require_customer)]


class PurchaseItem(StrictRequest):
    zone_id: UUID
    quantity: int = Field(strict=True, ge=1, le=100)
    seat_ids: list[UUID] = Field(default_factory=list, max_length=100)


class Purchase(StrictRequest):
    event_id: UUID
    items: list[PurchaseItem] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_items(self) -> Self:
        if len({i.zone_id for i in self.items}) != len(self.items):
            raise ValueError("Zones must be unique")
        seats = [s for i in self.items for s in i.seat_ids]
        if len(set(seats)) != len(seats) or sum(i.quantity for i in self.items) > 100:
            raise ValueError("Duplicate seats or too many tickets")
        return self

    def digest(self) -> str:
        # Pydantic is the inbound HTTP adapter; canonical identity belongs to the domain.
        intent = PurchaseIntent(
            event_id=self.event_id,
            items=tuple(TicketSelection(i.zone_id, i.quantity, tuple(i.seat_ids))
                        for i in self.items),
        )
        return intent.canonical_hash()


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_item_id: UUID
    zone_id: UUID
    seat_id: UUID | None
    status: str


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    zone_id: UUID
    quantity: int
    unit_price_minor: int
    subtotal_minor: int


class OrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    event_id: UUID
    status: str
    total_minor: int
    currency: str
    created_at: datetime
    items: list[ItemResponse]
    tickets: list[TicketResponse]


class TicketPage(BaseModel):
    items: list[TicketResponse]
    limit: int
    offset: int
    total: int



@router.post("/orders", response_model=OrderResponse, status_code=201)
def purchase(payload: Purchase, user: Customer, key: Key, db: Db,
             response: Response) -> OrderResponse:
    intent = PurchaseIntent(
        event_id=payload.event_id,
        items=tuple(
            TicketSelection(item.zone_id, item.quantity, tuple(item.seat_ids))
            for item in payload.items
        ),
    )
    unit_of_work = SqlAlchemyPurchaseUnitOfWork(db)
    try:
        outcome = purchase_tickets(intent, user.id, key, unit_of_work)
    except PurchaseKeyConflict as error:
        raise HTTPException(409, str(error)) from error
    except PurchaseError as error:
        raise HTTPException(error.status, error.detail) from error
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Purchase conflicts with inventory") from None
    response.status_code = 200 if outcome.replayed else 201
    response.headers["Idempotent-Replayed"] = "true" if outcome.replayed else "false"
    return OrderResponse.model_validate(outcome.order, from_attributes=True)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, user: CurrentUser, db: Db) -> OrderResponse:
    try:
        result = query_order(order_id, user.id, SqlAlchemyTicketQueries(db))
    except PurchaseError as error:
        raise HTTPException(error.status, error.detail) from error
    return OrderResponse.model_validate(result, from_attributes=True)


@router.get("/me/tickets", response_model=TicketPage)
def my_tickets(user: CurrentUser, db: Db, limit: Limit = 20, offset: Offset = 0) -> TicketPage:
    result = query_tickets(user.id, limit, offset, SqlAlchemyTicketQueries(db))
    return TicketPage.model_validate(result, from_attributes=True)
