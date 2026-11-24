"""Pure Events domain: no framework or database dependencies."""
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True)
class EventRecord:
    id: UUID
    owner_id: UUID
    name: str
    description: str
    venue: str
    start_at: datetime
    end_at: datetime
    status: str


def is_publicly_visible(event: EventRecord, now: datetime) -> bool:
    """Only future, published events appear in the public catalog."""
    starts = event.start_at.replace(tzinfo=UTC) if event.start_at.tzinfo is None else event.start_at
    return event.status == "published" and starts > now


def validate_event(event: EventRecord) -> None:
    if event.status not in {"draft", "published"}:
        raise ValueError("Invalid status")
    if not event.name.strip() or not event.venue.strip():
        raise ValueError("Name and venue required")
    if event.end_at <= event.start_at:
        raise ValueError("End must follow start")
