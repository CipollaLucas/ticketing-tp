"""Stage I draft editing use case, independent of HTTP and persistence.

The write port must lock the event row and commit atomically. The event cannot
be edited after publication; only owner or administrator is authorized.
"""
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from events_service.domain import EventRecord, validate_event


class EditEventError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


class DraftEditPort(Protocol):
    def locked_event(self, event_id: UUID) -> EventRecord | None: ...
    def pending_publication(self, event_id: UUID) -> bool: ...
    def save(self, value: EventRecord) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@dataclass(frozen=True)
class EventPatch:
    changes: dict[str, object]


EDITABLE = {"name", "description", "venue", "start_at", "end_at"}


def edit_draft(
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    patch: EventPatch,
    port: DraftEditPort,
    now: datetime,
) -> EventRecord:
    try:
        current = port.locked_event(event_id)
        if current is None:
            raise EditEventError(404, "Event not found")
        if actor_role not in {"event_owner", "administrator"}:
            raise EditEventError(403, "Event owner role required")
        if actor_role != "administrator" and current.owner_id != actor_id:
            raise EditEventError(403, "Resource belongs to another user")
        if current.status != "draft":
            raise EditEventError(409, "Unpublish the event before editing")
        if port.pending_publication(event_id):
            raise EditEventError(409, "Publication preparation is pending")
        if not patch.changes or not patch.changes.keys() <= EDITABLE:
            raise EditEventError(422, "Provide at least one editable event field")
        if any(value is None for value in patch.changes.values()):
            raise EditEventError(422, "Provide at least one non-null event field")
        # Explicitly typed updates: dynamic **dict expands into incompatible
        # EventRecord fields under mypy and would obscure the allowed schema.
        name = current.name
        description = current.description
        venue = current.venue
        start_at = current.start_at
        end_at = current.end_at
        for key, value in patch.changes.items():
            if key in {"name", "venue", "description"}:
                if not isinstance(value, str):
                    raise EditEventError(422, "Invalid event metadata")
                normalized = value.strip()
                if key == "name":
                    name = normalized
                elif key == "venue":
                    venue = normalized
                else:
                    description = normalized
            elif key in {"start_at", "end_at"}:
                if not isinstance(value, datetime) or value.tzinfo is None:
                    raise EditEventError(422, "Invalid event dates")
                try:
                    normalized_date = value.astimezone(UTC)
                except OverflowError as error:
                    raise EditEventError(422, "Invalid event dates") from error
                if key == "start_at":
                    start_at = normalized_date
                else:
                    end_at = normalized_date
            else:
                raise EditEventError(422, "Invalid event field")
        updated = replace(
            current, name=name, description=description, venue=venue,
            start_at=start_at, end_at=end_at, updated_at=now.astimezone(UTC),
        )
        if (
            updated.start_at.astimezone(UTC) <= now.astimezone(UTC)
            or updated.end_at.astimezone(UTC) <= updated.start_at.astimezone(UTC)
            or any("\x00" in field for field in (
                updated.name, updated.venue, updated.description,
            ))
            or len(updated.name) > 200 or len(updated.venue) > 300
            or len(updated.description) > 5000
        ):
            raise EditEventError(422, "Invalid event metadata or dates")
        try:
            validate_event(updated)
        except ValueError as error:
            raise EditEventError(422, "Invalid event metadata or dates") from error
        port.save(updated)
        port.commit()
        return updated
    except Exception:
        port.rollback()
        raise
