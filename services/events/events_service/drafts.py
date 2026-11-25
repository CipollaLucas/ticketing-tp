"""Hexagonal draft creation. No HTTP, SQLAlchemy, or token decoding here."""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from events_service.domain import EventRecord, validate_event


@dataclass(frozen=True)
class DraftInput:
    name: str
    description: str
    venue: str
    start_at: datetime
    end_at: datetime


class DraftWriter(Protocol):
    def add(self, event: EventRecord) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def create_draft(
    payload: DraftInput, owner_id: UUID, writer: DraftWriter, now: datetime,
) -> EventRecord:
    """Create a draft only for an already-authorized owner.

    The authenticated Identity principal must be supplied by a future inbound
    adapter; owner_id is never accepted directly from a public request.
    """
    start = payload.start_at
    end = payload.end_at
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Event dates must contain timezone information")
    if start.astimezone(UTC) <= now.astimezone(UTC):
        raise ValueError("Event start must be in the future")
    if "\x00" in (payload.name + payload.description + payload.venue):
        raise ValueError("Event text cannot contain NUL bytes")
    event = EventRecord(
        id=uuid4(), owner_id=owner_id, name=payload.name.strip(),
        description=payload.description.strip(), venue=payload.venue.strip(),
        start_at=start.astimezone(UTC), end_at=end.astimezone(UTC),
        status="draft", created_at=now.astimezone(UTC), updated_at=now.astimezone(UTC),
    )
    validate_event(event)
    if len(event.name) > 200 or len(event.venue) > 300 or len(event.description) > 5000:
        raise ValueError("Event text exceeds supported length")
    try:
        writer.add(event)
        writer.commit()
    except Exception:
        writer.rollback()
        raise
    return event
