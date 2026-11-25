"""Events-owned SQLAlchemy adapter. UUID owner_id has no external FK."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from events_service.domain import EventRecord
from events_service.publication import PublicationIntent
from events_service.settings import settings
from events_service.unpublish import UnpublishIntent


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="valid_event_status"),
        CheckConstraint("end_at > start_at", name="valid_event_dates"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(5000))
    venue: Mapped[str] = mapped_column(String(300))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC),
    )


engine = create_engine(settings.database_url, pool_pre_ping=True)


class SqlAlchemyEventReader:
    def __init__(self, session: Session):
        self.session = session

    def upcoming(self, now: datetime, limit: int, offset: int) -> tuple[list[EventRecord], int]:
        conditions = (EventRow.status == "published", EventRow.start_at > now)
        total = self.session.scalar(
            select(func.count()).select_from(EventRow).where(*conditions)
        ) or 0
        rows = self.session.scalars(
            select(EventRow).where(*conditions).order_by(EventRow.start_at, EventRow.id)
            .offset(offset).limit(limit)
        ).all()
        records = [
            EventRecord(
                id=row.id, owner_id=row.owner_id, name=row.name,
                description=row.description, venue=row.venue, start_at=row.start_at,
                end_at=row.end_at, status=row.status,
                created_at=row.created_at, updated_at=row.updated_at,
            )
            for row in rows
        ]
        return records, total


    def by_id(self, event_id: UUID) -> EventRecord | None:
        row = self.session.get(EventRow, event_id)
        if row is None:
            return None
        return EventRecord(
            id=row.id, owner_id=row.owner_id, name=row.name,
            description=row.description, venue=row.venue,
            start_at=row.start_at, end_at=row.end_at, status=row.status,
            created_at=row.created_at, updated_at=row.updated_at,
        )

    def by_owner(
        self, owner_id: UUID | None, limit: int, offset: int,
    ) -> tuple[list[EventRecord], int]:
        clauses = [EventRow.owner_id == owner_id] if owner_id is not None else []
        total = self.session.scalar(
            select(func.count()).select_from(EventRow).where(*clauses)
        ) or 0
        rows = self.session.scalars(
            select(EventRow).where(*clauses)
            .order_by(EventRow.start_at, EventRow.id).offset(offset).limit(limit)
        ).all()
        return [
            EventRecord(
                id=row.id, owner_id=row.owner_id, name=row.name,
                description=row.description, venue=row.venue, start_at=row.start_at,
                end_at=row.end_at, status=row.status,
                created_at=row.created_at, updated_at=row.updated_at,
            )
            for row in rows
        ], total


class SqlAlchemyDraftWriter:
    """Transactional outbound adapter used by the draft creation use case."""

    def __init__(self, session: Session):
        self.session = session

    def add(self, event: EventRecord) -> None:
        self.session.add(EventRow(
            id=event.id, owner_id=event.owner_id, name=event.name,
            description=event.description, venue=event.venue,
            start_at=event.start_at, end_at=event.end_at, status=event.status,
            created_at=event.created_at or datetime.now(UTC),
            updated_at=event.updated_at or datetime.now(UTC),
        ))

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class SqlAlchemyDraftEditPort:
    """Events-owned locked mutation, no cross-context database access."""

    def __init__(self, session: Session):
        self.session = session

    def locked_event(self, event_id: UUID) -> EventRecord | None:
        row = self.session.scalar(
            select(EventRow).where(EventRow.id == event_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            return None
        return EventRecord(
            id=row.id, owner_id=row.owner_id, name=row.name,
            description=row.description, venue=row.venue,
            start_at=row.start_at, end_at=row.end_at, status=row.status,
            created_at=row.created_at, updated_at=row.updated_at,
        )

    def pending_publication(self, event_id: UUID) -> bool:
        return self.session.get(PublicationIntentRow, event_id) is not None

    def save(self, event: EventRecord) -> None:
        row = self.session.get(EventRow, event.id)
        assert row is not None
        row.name = event.name
        row.description = event.description
        row.venue = event.venue
        row.start_at = event.start_at
        row.end_at = event.end_at
        assert event.updated_at is not None
        row.updated_at = event.updated_at

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class PublicationIntentRow(Base):
    __tablename__ = "event_publication_intents"
    __table_args__ = (
        CheckConstraint("phase IN ('prepared','metadata_published')", name="valid_publication_intent_phase"),
        CheckConstraint("event_revision >= 1", name="positive_publication_revision"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("events.id"), primary_key=True,
    )
    command_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False, default="prepared")
    expected_gate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SqlAlchemyPublicationUnitOfWork:
    """Events-local transaction only; no cross-service database references."""

    def __init__(self, session: Session):
        self.session = session

    def lock_event(self, event_id: UUID) -> EventRecord | None:
        row = self.session.scalar(
            select(EventRow).where(EventRow.id == event_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            return None
        return EventRecord(
            id=row.id, owner_id=row.owner_id, name=row.name,
            description=row.description, venue=row.venue,
            start_at=row.start_at, end_at=row.end_at, status=row.status,
            created_at=row.created_at, updated_at=row.updated_at,
        )

    def existing_intent(self, event_id: UUID) -> PublicationIntent | None:
        row = self.session.get(PublicationIntentRow, event_id)
        if row is None:
            return None
        return PublicationIntent(
            command_id=row.command_id, event_id=row.event_id,
            event_revision=row.event_revision, phase=row.phase,
            expected_gate_version=row.expected_gate_version,
        )

    def event_revision(self, event_id: UUID) -> int:
        row = self.session.get(EventRow, event_id)
        assert row is not None
        return row.revision

    def persist_intent(self, intent: PublicationIntent) -> None:
        self.session.add(PublicationIntentRow(
            event_id=intent.event_id, command_id=intent.command_id,
            event_revision=intent.event_revision, phase=intent.phase,
        ))

    def bind_gate_version(self, event_id: UUID, version: int) -> None:
        row = self.session.get(PublicationIntentRow, event_id)
        assert row is not None
        row.expected_gate_version = version

    def mark_metadata_published(
        self, event_id: UUID, revision: int, now: datetime,
    ) -> None:
        row = self.session.get(EventRow, event_id)
        intent = self.session.get(PublicationIntentRow, event_id)
        assert row is not None and intent is not None
        row.status = "published"
        row.revision = revision
        row.updated_at = now
        intent.phase = "metadata_published"
        old_close = self.session.get(UnpublishIntentRow, event_id)
        if old_close is not None:
            if old_close.phase != "completed":
                raise ValueError("Cannot publish during unpublish")
            self.session.delete(old_close)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class UnpublishIntentRow(Base):
    __tablename__ = "event_unpublish_intents"
    __table_args__ = (
        CheckConstraint("phase IN ('prepared','completed')", name="valid_unpublish_phase"),
        CheckConstraint("event_revision >= 1", name="positive_unpublish_revision"),
        CheckConstraint("expected_gate_version >= 0", name="positive_unpublish_gate_version"),
    )
    event_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("events.id"), primary_key=True,
    )
    command_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_gate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)


class SqlAlchemyUnpublishUnit:
    """Each method set is called within an Events-local SQL transaction."""

    def __init__(self, session: Session):
        self.session = session

    def lock_event(self, event_id: UUID) -> EventRecord | None:
        row = self.session.scalar(
            select(EventRow).where(EventRow.id == event_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            return None
        return EventRecord(
            id=row.id, owner_id=row.owner_id, name=row.name,
            description=row.description, venue=row.venue,
            start_at=row.start_at, end_at=row.end_at, status=row.status,
            created_at=row.created_at, updated_at=row.updated_at,
        )

    def event_revision(self, event_id: UUID) -> int:
        row = self.session.get(EventRow, event_id)
        assert row is not None
        return row.revision

    def existing_unpublish(self, event_id: UUID) -> UnpublishIntent | None:
        row = self.session.get(UnpublishIntentRow, event_id)
        if row is None:
            return None
        return UnpublishIntent(
            row.command_id, row.event_id, row.event_revision,
            row.expected_gate_version, row.phase,
        )

    def pending_publish(self, event_id: UUID) -> bool:
        row = self.session.get(PublicationIntentRow, event_id)
        return row is not None and row.phase == "prepared"

    def persist_unpublish(self, intent: UnpublishIntent) -> None:
        self.session.add(UnpublishIntentRow(
            command_id=intent.command_id, event_id=intent.event_id,
            event_revision=intent.event_revision,
            expected_gate_version=intent.expected_gate_version,
            phase=intent.phase,
        ))

    def finish_unpublish(self, intent: UnpublishIntent, now: datetime) -> None:
        row = self.session.get(EventRow, intent.event_id)
        closing = self.session.get(UnpublishIntentRow, intent.event_id)
        assert row is not None and closing is not None
        row.status = "draft"
        row.revision = intent.event_revision
        row.updated_at = now
        closing.phase = "completed"
        # The old publish command has no further effect on the new draft.
        # Removing it restores draft editing and allows a new publish revision.
        publishing = self.session.get(PublicationIntentRow, intent.event_id)
        if publishing is not None:
            self.session.delete(publishing)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
