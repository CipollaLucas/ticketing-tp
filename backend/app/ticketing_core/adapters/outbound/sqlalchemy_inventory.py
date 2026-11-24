"""Outbound SQLAlchemy adapter for inventory configuration and queries."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Role, Seat, Ticket, User, Zone
from app.ticketing_core.application.inventory import (
    InventoryView,
    SeatView,
    ZoneCommand,
    ZoneView,
)
from app.ticketing_core.application.ports import PurchaseError


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyInventoryAdapter:
    def __init__(self, db: Session):
        self.db = db

    def add_zone(self, event_id: UUID, actor_id: UUID, command: ZoneCommand) -> UUID:
        # Same event row lock used for publishing and buying.
        event = self.db.scalar(
            select(Event).where(Event.id == event_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if event is None:
            raise PurchaseError(404, "Event not found")
        user = self.db.get(User, actor_id)
        assert user is not None
        self.db.refresh(user)
        if user.role not in (Role.EVENT_OWNER, Role.ADMINISTRATOR):
            raise PurchaseError(403, "Event owner role required")
        if user.id != event.owner_id and user.role != Role.ADMINISTRATOR:
            raise PurchaseError(403, "Resource belongs to another user")
        if event.status != "draft" or utc(event.start_at) <= datetime.now(UTC):
            raise PurchaseError(409, "Inventory requires a future draft")
        zone = Zone(
            event_id=event.id, name=command.name, mode=command.mode,
            price_minor=command.price_minor, currency=command.currency,
            capacity=command.capacity, available=command.capacity,
        )
        self.db.add(zone)
        self.db.flush()
        self.db.add_all([Seat(zone_id=zone.id, label=label) for label in command.seats])
        return zone.id

    def read_zone(self, zone_id: UUID) -> ZoneView:
        zone = self.db.get(Zone, zone_id)
        assert zone is not None
        seats = self.db.scalars(
            select(Seat).where(Seat.zone_id == zone.id).order_by(Seat.label)
        ).all()
        sold = set(self.db.scalars(
            select(Ticket.seat_id).where(
                Ticket.zone_id == zone.id, Ticket.seat_id.is_not(None)
            )
        ).all())
        return ZoneView(
            id=zone.id, name=zone.name, mode=zone.mode,
            price_minor=zone.price_minor, currency=zone.currency,
            capacity=zone.capacity,
            available=zone.available if zone.available is not None else len(seats)-len(sold),
            seats=tuple(
                SeatView(id=seat.id, label=seat.label, available=seat.id not in sold)
                for seat in seats
            ),
        )

    def read_inventory(self, event_id: UUID, actor_id: UUID | None) -> InventoryView:
        event = self.db.get(Event, event_id)
        if event is None:
            raise PurchaseError(404, "Event not found")
        if actor_id is None:
            if event.status != "published":
                raise PurchaseError(404, "Event not found")
        else:
            actor = self.db.get(User, actor_id)
            assert actor is not None
            if actor.role not in (Role.EVENT_OWNER, Role.ADMINISTRATOR):
                raise PurchaseError(403, "Event owner role required")
            if actor.id != event.owner_id and actor.role != Role.ADMINISTRATOR:
                raise PurchaseError(403, "Resource belongs to another user")
        zones = self.db.scalars(
            select(Zone).where(Zone.event_id == event_id).order_by(Zone.name)
        ).all()
        return InventoryView(event_id=event_id, zones=tuple(self.read_zone(z.id) for z in zones))

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
