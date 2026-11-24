from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(StrEnum):
    CUSTOMER = "customer"
    EVENT_OWNER = "event_owner"
    ADMINISTRATOR = "administrator"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('customer', 'event_owner', 'administrator')", name="valid_user_role"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.CUSTOMER.value)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="valid_event_status"),
        CheckConstraint("end_at > start_at", name="valid_event_dates"),
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="valid_event_name"),
        CheckConstraint("length(trim(venue)) BETWEEN 1 AND 300", name="valid_event_venue"),
        CheckConstraint("length(description) <= 5000", name="valid_event_description"),
        Index("ix_events_catalog", "status", "start_at", "id"),
        Index("ix_events_owner", "owner_id", "start_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(5000))
    venue: Mapped[str] = mapped_column(String(300))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Zone(Base):
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
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(8))
    price_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    capacity: Mapped[int | None] = mapped_column(Integer)
    available: Mapped[int | None] = mapped_column(Integer)


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("zone_id", "label", name="uq_seat_zone_label"),
        UniqueConstraint("id", "zone_id", name="uq_seat_id_zone"),
        ForeignKeyConstraint(["zone_id", "mode"], ["zones.id", "zones.mode"]),
        CheckConstraint("mode = 'numbered'", name="valid_seat_mode"),
        CheckConstraint("length(trim(label)) BETWEEN 1 AND 50", name="valid_seat_label"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    zone_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    mode: Mapped[str] = mapped_column(String(8), default="numbered")
    label: Mapped[str] = mapped_column(String(50))
