"""Recoverable Events unpublish, with Ticketing as authority for sales.

Closing must be confirmed by Ticketing's atomic no-sales endpoint BEFORE
Events changes published metadata to draft. A lost ACK is retried using a
durable command ID and expected gate version, never a fresh close command.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from events_service.domain import EventRecord
from events_service.sales_port import (
    SaleGateCommand,
    SaleGatePort,
    SaleGateState,
    SaleGateUnavailable,
)


class UnpublishRejected(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class UnpublishIntent:
    command_id: UUID
    event_id: UUID
    event_revision: int
    expected_gate_version: int
    phase: str


class UnpublishUnit(Protocol):
    def lock_event(self, event_id: UUID) -> EventRecord | None: ...
    def event_revision(self, event_id: UUID) -> int: ...
    def existing_unpublish(self, event_id: UUID) -> UnpublishIntent | None: ...
    def pending_publish(self, event_id: UUID) -> bool: ...
    def persist_unpublish(self, intent: UnpublishIntent) -> None: ...
    def finish_unpublish(self, intent: UnpublishIntent, now: datetime) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def authorize(event: EventRecord | None, actor_id: UUID, role: str) -> EventRecord:
    if event is None:
        raise UnpublishRejected(404, "Event not found")
    if role not in {"event_owner", "administrator"}:
        raise UnpublishRejected(403, "Event owner role required")
    if role != "administrator" and actor_id != event.owner_id:
        raise UnpublishRejected(403, "Resource belongs to another user")
    return event


def prepare_unpublish(
    unit: UnpublishUnit,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    gate: SaleGateState,
) -> UnpublishIntent:
    """Persist versioned close intent, never perform remote work under DB lock."""
    try:
        event = authorize(unit.lock_event(event_id), actor_id, actor_role)
        prior = unit.existing_unpublish(event_id)
        if prior is not None:
            if prior.phase not in {"prepared", "completed"}:
                raise UnpublishRejected(409, "Unpublish command in unknown phase")
            unit.commit()
            return prior
        if event.status != "published":
            raise UnpublishRejected(409, "Event is not published")
        if unit.pending_publish(event_id):
            raise UnpublishRejected(409, "Publication confirmation still pending")
        revision = unit.event_revision(event_id)
        if (
            gate.event_id != event_id or gate.state != "open"
            or gate.version < 0 or gate.event_revision != revision
        ):
            raise UnpublishRejected(409, "Ticketing gate is not a confirmed open sale")
        intent = UnpublishIntent(
            uuid4(), event_id, revision + 1, gate.version, "prepared",
        )
        unit.persist_unpublish(intent)
        unit.commit()
        return intent
    except Exception:
        unit.rollback()
        raise


def complete_unpublish(
    unit: UnpublishUnit,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    intent: UnpublishIntent,
    ack: SaleGateState,
    now: datetime,
) -> UnpublishIntent:
    """No metadata mutation is allowed without a matching durable close ACK."""
    try:
        event = authorize(unit.lock_event(event_id), actor_id, actor_role)
        stored = unit.existing_unpublish(event_id)
        if stored != intent:
            raise UnpublishRejected(409, "Unpublish intent changed")
        if stored.phase == "completed":
            if event.status != "draft" or unit.event_revision(event_id) != intent.event_revision:
                raise UnpublishRejected(409, "Unpublish completion inconsistent")
            unit.commit()
            return stored
        if (
            stored.phase != "prepared" or event.status != "published"
            or unit.event_revision(event_id) + 1 != intent.event_revision
            or ack.event_id != event_id or ack.state != "closed"
            or ack.version != intent.expected_gate_version + 1
            or ack.event_revision != intent.event_revision
        ):
            raise UnpublishRejected(409, "No matching confirmed gate close")
        unit.finish_unpublish(intent, now.astimezone(UTC))
        unit.commit()
        return UnpublishIntent(
            intent.command_id, event_id, intent.event_revision,
            intent.expected_gate_version, "completed",
        )
    except Exception:
        unit.rollback()
        raise


def unpublish_via_ticketing(
    unit: UnpublishUnit,
    gate: SaleGatePort,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    now: datetime,
    request_id: str | None = None,
) -> UnpublishIntent:
    """Read first, store close intent, close atomically in Ticketing, then draft."""
    # An open-state read alone is not authorization: Events rechecks under its
    # own lock and Ticketing independently enforces CAS and no-confirmed-sales.
    current = gate.state(event_id, request_id)
    intent = prepare_unpublish(unit, event_id, actor_id, actor_role, current)
    if intent.phase == "completed":
        return intent
    command = SaleGateCommand(
        event_id, intent.command_id, "close",
        intent.expected_gate_version, intent.event_revision,
    )
    ack = gate.close_without_sales(command, request_id)
    if ack.event_id != event_id or ack.state != "closed":
        raise SaleGateUnavailable("Ticketing did not confirm sales closure")
    return complete_unpublish(
        unit, event_id, actor_id, actor_role, intent, ack, now,
    )
