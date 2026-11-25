"""Ticketing-owned DB. No Events or Identity tables, imports or foreign keys."""

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ticketing_service.domain import GateCommand, GateState, SaleState
from ticketing_service.settings import settings


class Base(DeclarativeBase):
    pass


class SaleGateRow(Base):
    __tablename__ = "sale_gates"
    __table_args__ = (
        CheckConstraint("state IN ('closed','open')", name="valid_sale_gate_state"),
        CheckConstraint("version >= 0", name="nonnegative_sale_gate_version"),
        CheckConstraint("event_revision >= 0", name="nonnegative_metadata_revision"),
    )
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="closed")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class GateCommandRow(Base):
    __tablename__ = "sale_gate_commands"
    command_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sale_gates.event_id"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_state: Mapped[str] = mapped_column(String(8), nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)


class ZoneRow(Base):
    """Ticketing owns zones; event_id is a cross-context UUID, not an FK."""

    __tablename__ = "zones"
    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_zone_event_name"),
        UniqueConstraint("id", "mode", name="uq_zone_id_mode"),
        CheckConstraint("mode IN ('general', 'numbered')", name="valid_zone_mode"),
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 100", name="valid_zone_name"),
        CheckConstraint("price_minor BETWEEN 0 AND 2147483647", name="valid_zone_price"),
        CheckConstraint("currency IN ('ARS', 'USD', 'EUR')", name="valid_zone_currency"),
        CheckConstraint(
            "(mode = 'general' AND capacity IS NOT NULL AND available IS NOT NULL "
            "AND capacity BETWEEN 1 AND 1000000 AND available BETWEEN 0 AND capacity) OR "
            "(mode = 'numbered' AND capacity IS NULL AND available IS NULL)",
            name="valid_zone_capacity",
        ),
        Index("ix_zones_event_id", "event_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SeatRow(Base):
    """Composite FK ensures a seat can belong only to a numbered zone."""

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("zone_id", "label", name="uq_seat_zone_label"),
        UniqueConstraint("id", "zone_id", name="uq_seat_id_zone"),
        ForeignKeyConstraint(
            ["zone_id", "mode"],
            ["zones.id", "zones.mode"],
            name="fk_seat_numbered_zone",
        ),
        CheckConstraint("mode = 'numbered'", name="valid_seat_mode"),
        CheckConstraint("length(trim(label)) BETWEEN 1 AND 50", name="valid_seat_label"),
        Index("ix_seats_zone_id", "zone_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    zone_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="numbered")
    label: Mapped[str] = mapped_column(String(50), nullable=False)


class OrderRow(Base):
    """Customer and Event UUID references remain outside Ticketing's FK graph."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key", name="uq_order_idempotency"),
        CheckConstraint("total_minor >= 0", name="valid_order_total"),
        CheckConstraint("currency IN ('ARS', 'USD', 'EUR')", name="valid_order_currency"),
        CheckConstraint("status = 'confirmed'", name="valid_order_status"),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_event_id", "event_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    customer_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class OrderItemRow(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "zone_id", name="uq_item_order_zone"),
        UniqueConstraint("id", "zone_id", name="uq_item_id_zone"),
        CheckConstraint("quantity BETWEEN 1 AND 100", name="valid_item_quantity"),
        CheckConstraint("unit_price_minor >= 0", name="valid_item_price"),
        CheckConstraint(
            "subtotal_minor = quantity * unit_price_minor",
            name="valid_item_subtotal",
        ),
        Index("ix_order_items_order_id", "order_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("zones.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)


class TicketRow(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_item_id", "zone_id"],
            ["order_items.id", "order_items.zone_id"],
        ),
        ForeignKeyConstraint(["seat_id", "zone_id"], ["seats.id", "seats.zone_id"]),
        CheckConstraint("status = 'valid'", name="valid_ticket_status"),
        Index("ix_tickets_order_item_id", "order_item_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    order_item_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("zones.id"), nullable=False)
    seat_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(5), nullable=False, default="valid")


engine = create_engine(settings.database_url, pool_pre_ping=True)


class SqlAlchemyGateUnitOfWork:
    def __init__(self, session: Session):
        self.db = session

    def previous_command(self, command: GateCommand) -> tuple[GateCommand, GateState] | None:
        row = self.db.get(GateCommandRow, command.command_id)
        if row is None:
            return None
        old = GateCommand(
            row.command_id,
            row.event_id,
            cast(Literal["open", "close"], row.action),
            row.expected_version,
            row.event_revision,
        )
        result = GateState(
            row.event_id, cast(SaleState, row.result_state), row.result_version, row.result_revision
        )
        return old, result

    def lock_gate(self, event_id: UUID) -> GateState | None:
        row = self.db.scalar(
            select(SaleGateRow)
            .where(SaleGateRow.event_id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            return None
        return GateState(row.event_id, cast(SaleState, row.state), row.version, row.event_revision)

    def confirmed_order_exists(self, event_id: UUID) -> bool:
        # Invoked ONLY after lock_gate while this transaction holds FOR UPDATE.
        return (
            self.db.scalar(
                select(OrderRow.id)
                .where(
                    OrderRow.event_id == event_id,
                    OrderRow.status == "confirmed",
                )
                .limit(1)
            )
            is not None
        )

    def save(self, command: GateCommand, state: GateState) -> None:
        row = self.db.get(SaleGateRow, state.event_id)
        assert row is not None
        row.state = state.state
        row.version = state.version
        row.event_revision = state.event_revision
        self.db.add(
            GateCommandRow(
                command_id=command.command_id,
                event_id=command.event_id,
                action=command.action,
                expected_version=command.expected_version,
                event_revision=command.event_revision,
                result_state=state.state,
                result_version=state.version,
                result_revision=state.event_revision,
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
