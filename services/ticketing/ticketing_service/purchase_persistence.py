"""Ticketing-only purchase UoW: a single PostgreSQL transaction for every write."""
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ticketing_service.persistence import (
    OrderItemRow,
    OrderRow,
    SaleGateRow,
    SeatRow,
    TicketRow,
    ZoneRow,
)
from ticketing_service.purchase import PurchaseError, PurchaseIntent
from ticketing_service.purchase_application import (
    OrderLineRecord,
    OrderRecord,
    TicketRecord,
)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyPurchaseUnitOfWork:
    def __init__(self, db: Session):
        self.db = db

    def lock_customer_key(self, customer_id: UUID) -> None:
        # Transaction-scoped advisory lock serializes idempotency keys for this
        # customer without accessing/locking a remote Identity user row.
        # Collisions only reduce concurrency, never allow duplicate purchases.
        key = customer_id.int & ((1 << 63) - 1)
        self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def find_existing(self, customer_id: UUID, key: str) -> tuple[UUID, str] | None:
        row = self.db.scalar(select(OrderRow).where(
            OrderRow.customer_id == customer_id,
            OrderRow.idempotency_key == key,
        ))
        return (row.id, row.request_hash) if row else None

    def allocate(self, customer_id: UUID, key: str, intent: PurchaseIntent) -> UUID:
        # SAME exact sale_gates row lock as close_sale_gate. Held through commit.
        gate = self.db.scalar(select(SaleGateRow).where(
            SaleGateRow.event_id == intent.event_id,
        ).with_for_update().execution_options(populate_existing=True))
        if gate is None or gate.state != "open":
            raise PurchaseError(409, "Event is not on sale")

        allocations: list[tuple[ZoneRow, object]] = []
        for item in sorted(intent.items, key=lambda x: x.zone_id):
            zone = self.db.scalar(
                select(ZoneRow).where(
                    ZoneRow.id == item.zone_id, ZoneRow.event_id == intent.event_id,
                ).with_for_update().execution_options(populate_existing=True)
            )
            if zone is None:
                raise PurchaseError(404, "Zone not found in event")
            if zone.mode == "general":
                if item.seat_ids:
                    raise PurchaseError(422, "General zone does not accept seats")
                updated = self.db.scalar(
                    update(ZoneRow).where(
                        ZoneRow.id == zone.id, ZoneRow.available >= item.quantity,
                    ).values(available=ZoneRow.available - item.quantity)
                    .returning(ZoneRow.id)
                )
                if updated is None:
                    raise PurchaseError(409, "Insufficient capacity")
            else:
                if len(item.seat_ids) != item.quantity:
                    raise PurchaseError(422, "Quantity must equal selected seats")
                seat_ids = self.db.scalars(select(SeatRow.id).where(
                    SeatRow.zone_id == zone.id, SeatRow.id.in_(item.seat_ids),
                )).all()
                if len(seat_ids) != item.quantity:
                    raise PurchaseError(422, "Seat does not belong to zone")
                if self.db.scalar(select(TicketRow.id).where(
                    TicketRow.seat_id.in_(item.seat_ids),
                ).limit(1)):
                    raise PurchaseError(409, "Seat already sold")
            allocations.append((zone, item))

        currencies = {zone.currency for zone, _ in allocations}
        if len(currencies) != 1:
            raise PurchaseError(422, "Order requires a single currency")
        order_id = uuid4()
        self.db.add(OrderRow(
            id=order_id, customer_id=customer_id, event_id=intent.event_id,
            idempotency_key=key, request_hash=intent.canonical_hash(),
            total_minor=sum(zone.price_minor * item.quantity for zone, item in allocations),
            currency=allocations[0][0].currency, status="confirmed",
            created_at=datetime.now(UTC),
        ))
        self.db.flush()
        for zone, item in allocations:
            item_id = uuid4()
            self.db.add(OrderItemRow(
                id=item_id, order_id=order_id, zone_id=zone.id,
                quantity=item.quantity, unit_price_minor=zone.price_minor,
                subtotal_minor=zone.price_minor * item.quantity,
            ))
            self.db.flush()
            self.db.add_all([
                TicketRow(
                    id=uuid4(), order_item_id=item_id, zone_id=zone.id,
                    seat_id=seat_id, status="valid",
                )
                for seat_id in (
                    item.seat_ids if item.seat_ids else (None,) * item.quantity
                )
            ])
        self.db.flush()
        return order_id

    def read_order(self, order_id: UUID) -> OrderRecord:
        order = self.db.get(OrderRow, order_id)
        assert order is not None
        items = self.db.scalars(select(OrderItemRow).where(
            OrderItemRow.order_id == order_id,
        ).order_by(OrderItemRow.zone_id)).all()
        tickets = self.db.scalars(
            select(TicketRow).join(
                OrderItemRow, TicketRow.order_item_id == OrderItemRow.id,
            ).where(OrderItemRow.order_id == order_id).order_by(TicketRow.id)
        ).all()
        return OrderRecord(
            id=order.id, customer_id=order.customer_id, event_id=order.event_id,
            status=order.status, total_minor=order.total_minor,
            currency=order.currency, created_at=utc(order.created_at),
            items=tuple(OrderLineRecord(
                id=line.id, zone_id=line.zone_id, quantity=line.quantity,
                unit_price_minor=line.unit_price_minor,
                subtotal_minor=line.subtotal_minor,
            ) for line in items),
            tickets=tuple(TicketRecord(
                id=ticket.id, order_item_id=ticket.order_item_id,
                zone_id=ticket.zone_id, seat_id=ticket.seat_id,
                status=ticket.status,
            ) for ticket in tickets),
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
