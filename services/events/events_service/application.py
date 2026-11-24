"""Application use case depends on the repository port, not SQLAlchemy."""
from datetime import datetime
from typing import Protocol

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
