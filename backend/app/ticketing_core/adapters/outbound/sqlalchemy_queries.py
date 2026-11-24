"""SQLAlchemy read-side adapter for order receipts and customer tickets."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Role, Ticket, User
from app.ticketing_core.adapters.outbound.sqlalchemy_purchase import (
    SqlAlchemyPurchaseUnitOfWork,
)
from app.ticketing_core.application.ports import OrderRecord, PurchaseError, TicketRecord
from app.ticketing_core.application.queries import TicketResultPage


class SqlAlchemyTicketQueries:
    def __init__(self, db: Session):
        self.db = db

    def get_order(self, order_id: UUID, actor_id: UUID) -> OrderRecord:
        order = self.db.get(Order, order_id)
        if order is None:
            raise PurchaseError(404, "Order not found")
        actor = self.db.get(User, actor_id)
        assert actor is not None
        if actor.id != order.customer_id and actor.role != Role.ADMINISTRATOR:
            raise PurchaseError(403, "Resource belongs to another user")
        return SqlAlchemyPurchaseUnitOfWork(self.db).read_order(order_id)

    def my_tickets(
        self, actor_id: UUID, limit: int, offset: int,
    ) -> TicketResultPage:
        query = (
            select(Ticket)
            .join(OrderItem, Ticket.order_item_id == OrderItem.id)
            .join(Order)
            .where(Order.customer_id == actor_id)
        )
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        tickets = self.db.scalars(
            query.order_by(Ticket.id).limit(limit).offset(offset)
        ).all()
        return TicketResultPage(
            items=tuple(TicketRecord(
                id=t.id, order_item_id=t.order_item_id, zone_id=t.zone_id,
                seat_id=t.seat_id, status=t.status,
            ) for t in tickets),
            total=total, limit=limit, offset=offset,
        )
