"""Atomic simulated purchases; PostgreSQL is the concurrency authority."""
from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, Db, StrictRequest, require_owner_or_admin
from app.events import Limit, Offset, utc
from app.models import Event, Order, OrderItem, Role, Seat, Ticket, User, Zone
from app.ticketing_core.domain.purchase import (
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
    assert_replay_compatible,
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


def order_response(order: Order, db: Db) -> OrderResponse:
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)
                       .order_by(OrderItem.zone_id)).all()
    tickets = db.scalars(select(Ticket).join(OrderItem, Ticket.order_item_id == OrderItem.id)
                         .where(OrderItem.order_id == order.id).order_by(Ticket.id)).all()
    return OrderResponse(
        id=order.id, customer_id=order.customer_id, event_id=order.event_id,
        status=order.status, total_minor=order.total_minor, currency=order.currency,
        created_at=utc(order.created_at), items=[ItemResponse.model_validate(i) for i in items],
        tickets=[TicketResponse.model_validate(t) for t in tickets],
    )


def allocate(payload: Purchase, user: User, key: str, db: Db) -> Order:
    event = db.scalar(select(Event).where(Event.id == payload.event_id).with_for_update()
                      .execution_options(populate_existing=True))
    if event is None:
        raise HTTPException(404, "Event not found")
    if event.status != "published" or utc(event.start_at) <= datetime.now(UTC):
        raise HTTPException(409, "Event is not on sale")
    allocations: list[tuple[Zone, PurchaseItem]] = []
    for item in sorted(payload.items, key=lambda i: i.zone_id):
        zone = db.scalar(select(Zone).where(Zone.id == item.zone_id,
                                            Zone.event_id == event.id).with_for_update()
                         .execution_options(populate_existing=True))
        if zone is None:
            raise HTTPException(404, "Zone not found in event")
        if zone.mode == "general":
            if item.seat_ids:
                raise HTTPException(422, "General zone does not accept seats")
            allocated = db.scalar(update(Zone).where(Zone.id == zone.id,
                              Zone.available >= item.quantity)
                              .values(available=Zone.available - item.quantity).returning(Zone.id))
            if allocated is None:
                raise HTTPException(409, "Insufficient capacity")
        else:
            if len(item.seat_ids) != item.quantity:
                raise HTTPException(422, "Quantity must equal selected seats")
            seats = db.scalars(select(Seat.id).where(Seat.zone_id == zone.id,
                                                     Seat.id.in_(item.seat_ids))).all()
            if len(seats) != item.quantity:
                raise HTTPException(422, "Seat does not belong to zone")
            if db.scalar(select(Ticket.id).where(Ticket.seat_id.in_(item.seat_ids)).limit(1)):
                raise HTTPException(409, "Seat already sold")
        allocations.append((zone, item))
    if len({zone.currency for zone, _ in allocations}) != 1:
        raise HTTPException(422, "Order requires a single currency")
    order = Order(customer_id=user.id, event_id=event.id, idempotency_key=key,
                  request_hash=payload.digest(), currency=allocations[0][0].currency,
                  total_minor=sum(z.price_minor * i.quantity for z, i in allocations))
    db.add(order)
    db.flush()
    for zone, item in allocations:
        line = OrderItem(order_id=order.id, zone_id=zone.id, quantity=item.quantity,
                         unit_price_minor=zone.price_minor,
                         subtotal_minor=zone.price_minor * item.quantity)
        db.add(line)
        db.flush()
        ids: list[UUID | None] = list(item.seat_ids) if item.seat_ids else [None]*item.quantity
        db.add_all([Ticket(order_item_id=line.id, zone_id=zone.id, seat_id=s) for s in ids])
    return order


@router.post("/orders", response_model=OrderResponse, status_code=201)
def purchase(payload: Purchase, user: Customer, key: Key, db: Db,
             response: Response) -> OrderResponse:
    try:
        # Serializes idempotency across events and rechecks role after lock waits.
        locked = db.scalar(select(User).where(User.id == user.id).with_for_update()
                           .execution_options(populate_existing=True))
        assert locked is not None
        require_customer(locked)
        existing = db.scalar(select(Order).where(Order.customer_id == user.id,
                                                 Order.idempotency_key == key))
        if existing is not None:
            try:
                assert_replay_compatible(existing.request_hash, payload.digest())
            except PurchaseKeyConflict as error:
                raise HTTPException(409, str(error)) from error
            result = order_response(existing, db)
            db.commit()
            response.status_code = 200
            response.headers["Idempotent-Replayed"] = "true"
            return result
        order = allocate(payload, user, key, db)
        db.flush()
        result = order_response(order, db)
        db.commit()
        response.headers["Idempotent-Replayed"] = "false"
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Purchase conflicts with inventory") from None
    except Exception:
        db.rollback()
        raise


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, user: CurrentUser, db: Db) -> OrderResponse:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    require_owner_or_admin(user, order.customer_id)
    return order_response(order, db)


@router.get("/me/tickets", response_model=TicketPage)
def my_tickets(user: CurrentUser, db: Db, limit: Limit = 20, offset: Offset = 0) -> TicketPage:
    query = select(Ticket).join(OrderItem, Ticket.order_item_id == OrderItem.id).join(Order).where(
        Order.customer_id == user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    tickets = db.scalars(query.order_by(Ticket.id).limit(limit).offset(offset)).all()
    return TicketPage(items=[TicketResponse.model_validate(t) for t in tickets],
                      total=total, limit=limit, offset=offset)
