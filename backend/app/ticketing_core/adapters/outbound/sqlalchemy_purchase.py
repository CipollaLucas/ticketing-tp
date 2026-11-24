"""SQLAlchemy outbound Unit of Work. Owns all database locks and persistence.

The purchase use case does not depend on SQLAlchemy or FastAPI.
"""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Event, Order, OrderItem, Role, Seat, Ticket, User, Zone
from app.ticketing_core.application.ports import (
    OrderLineRecord,
    OrderRecord,
    PurchaseError,
    TicketRecord,
)
from app.ticketing_core.domain.purchase import PurchaseIntent


def to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyPurchaseUnitOfWork:
    def __init__(self, db: Session):
        self.db = db

    def lock_customer(self, customer_id: UUID) -> None:
        # Lock customer row before key lookup, even across different events.
        user = self.db.scalar(
            select(User).where(User.id == customer_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None or user.role != Role.CUSTOMER:
            raise PurchaseError(403, "Customer role required")

    def find_existing(self, customer_id: UUID, key: str) -> tuple[UUID, str] | None:
        existing = self.db.scalar(
            select(Order).where(
                Order.customer_id == customer_id, Order.idempotency_key == key
            )
        )
        return (existing.id, existing.request_hash) if existing is not None else None

    def allocate(self, customer_id: UUID, key: str, intent: PurchaseIntent) -> UUID:
        event = self.db.scalar(
            select(Event).where(Event.id == intent.event_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if event is None:
            raise PurchaseError(404, "Event not found")
        if event.status != "published" or to_utc(event.start_at) <= datetime.now(UTC):
            raise PurchaseError(409, "Event is not on sale")

        allocations = []
        for item in sorted(intent.items, key=lambda entry: entry.zone_id):
            zone = self.db.scalar(
                select(Zone).where(Zone.id == item.zone_id, Zone.event_id == event.id)
                .with_for_update().execution_options(populate_existing=True)
            )
            if zone is None:
                raise PurchaseError(404, "Zone not found in event")
            if zone.mode == "general":
                if item.seat_ids:
                    raise PurchaseError(422, "General zone does not accept seats")
                allocated = self.db.scalar(
                    update(Zone).where(
                        Zone.id == zone.id, Zone.available >= item.quantity
                    ).values(available=Zone.available - item.quantity).returning(Zone.id)
                )
                if allocated is None:
                    raise PurchaseError(409, "Insufficient capacity")
            else:
                if len(item.seat_ids) != item.quantity:
                    raise PurchaseError(422, "Quantity must equal selected seats")
                seats = self.db.scalars(
                    select(Seat.id).where(
                        Seat.zone_id == zone.id, Seat.id.in_(item.seat_ids)
                    )
                ).all()
                if len(seats) != item.quantity:
                    raise PurchaseError(422, "Seat does not belong to zone")
                if self.db.scalar(
                    select(Ticket.id).where(Ticket.seat_id.in_(item.seat_ids)).limit(1)
                ):
                    raise PurchaseError(409, "Seat already sold")
            allocations.append((zone, item))

        if len({zone.currency for zone, _ in allocations}) != 1:
            raise PurchaseError(422, "Order requires a single currency")

        order = Order(
            customer_id=customer_id,
            event_id=event.id,
            idempotency_key=key,
            request_hash=intent.canonical_hash(),
            currency=allocations[0][0].currency,
            total_minor=sum(zone.price_minor * item.quantity for zone, item in allocations),
        )
        self.db.add(order)
        self.db.flush()
        for zone, item in allocations:
            line = OrderItem(
                order_id=order.id, zone_id=zone.id, quantity=item.quantity,
                unit_price_minor=zone.price_minor,
                subtotal_minor=zone.price_minor * item.quantity,
            )
            self.db.add(line)
            self.db.flush()
            seat_ids: list[UUID | None] = (
                list(item.seat_ids) if item.seat_ids else [None] * item.quantity
            )
            self.db.add_all(
                [Ticket(order_item_id=line.id, zone_id=zone.id, seat_id=seat)
                 for seat in seat_ids]
            )
        self.db.flush()
        return order.id

    def read_order(self, order_id: UUID) -> OrderRecord:
        order = self.db.get(Order, order_id)
        assert order is not None
        items = self.db.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)
            .order_by(OrderItem.zone_id)
        ).all()
        tickets = self.db.scalars(
            select(Ticket).join(OrderItem, Ticket.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order.id).order_by(Ticket.id)
        ).all()
        return OrderRecord(
            id=order.id, customer_id=order.customer_id, event_id=order.event_id,
            status=order.status, total_minor=order.total_minor,
            currency=order.currency, created_at=to_utc(order.created_at),
            items=tuple(
                OrderLineRecord(
                    id=item.id, zone_id=item.zone_id, quantity=item.quantity,
                    unit_price_minor=item.unit_price_minor,
                    subtotal_minor=item.subtotal_minor,
                ) for item in items
            ),
            tickets=tuple(
                TicketRecord(
                    id=ticket.id, order_item_id=ticket.order_item_id,
                    zone_id=ticket.zone_id, seat_id=ticket.seat_id,
                    status=ticket.status,
                ) for ticket in tickets
            ),
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
