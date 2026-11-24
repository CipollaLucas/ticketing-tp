"""Application use case depends on the repository port, not SQLAlchemy."""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from events_service.domain import EventRecord, is_publicly_visible


class EventReader(Protocol):
    def upcoming(self, now: datetime, limit: int, offset: int) -> tuple[list[EventRecord], int]: ...


def public_catalog(reader: EventReader, now: datetime, limit: int = 20,
                   offset: int = 0) -> tuple[list[EventRecord], int]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid pagination")
    events, count = reader.upcoming(now, limit, offset)
    if not all(is_publicly_visible(event, now) for event in events):
        raise ValueError("Repository returned a non-public event")
    return events, count


class OwnedEventReader(Protocol):
    def by_owner(
        self, owner_id: UUID | None, limit: int, offset: int,
    ) -> tuple[list[EventRecord], int]: ...


def owned_events(
    reader: OwnedEventReader, owner_id: UUID | None,
    limit: int = 20, offset: int = 0,
) -> tuple[list[EventRecord], int]:
    """Read the authorized owner's events, including drafts.

    None means administrator scope; the HTTP adapter must derive that choice
    from a freshly verified Identity principal, never from query parameters.
    """
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid pagination")
    rows, total = reader.by_owner(owner_id, limit, offset)
    if owner_id is not None and any(row.owner_id != owner_id for row in rows):
        raise ValueError("Repository returned another owner's event")
    return rows, total
