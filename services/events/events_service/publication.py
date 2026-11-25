"""Durable preparation of an Events publication, without opening sales.

This is the first half of Stage I publish migration. An intent is persisted
before any cross-service call, so its command_id and revision can be retried.
No HTTP route or remote sale-gate invocation is introduced here.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from events_service.domain import EventRecord
from events_service.sales_port import SaleGateState


class PublicationRejected(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class PublicationIntent:
    command_id: UUID
    event_id: UUID
    event_revision: int
    phase: str
    expected_gate_version: int | None = None


class PublicationUnitOfWork(Protocol):
    def lock_event(self, event_id: UUID) -> EventRecord | None: ...
    def existing_intent(self, event_id: UUID) -> PublicationIntent | None: ...
    def event_revision(self, event_id: UUID) -> int: ...
    def persist_intent(self, intent: PublicationIntent) -> None: ...
    def bind_gate_version(self, event_id: UUID, version: int) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def prepare_publication(
    unit: PublicationUnitOfWork,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    now: datetime,
) -> PublicationIntent:
    """Store one stable pending command under the Events row lock.

    Replays return the same command ID, not a new transition. This transaction
    intentionally does not update Event.status or contact Ticketing.
    """
    try:
        event = unit.lock_event(event_id)
        if event is None:
            raise PublicationRejected(404, "Event not found")
        if actor_role not in {"event_owner", "administrator"}:
            raise PublicationRejected(403, "Event owner role required")
        if actor_role != "administrator" and actor_id != event.owner_id:
            raise PublicationRejected(403, "Resource belongs to another user")
        if event.status != "draft":
            raise PublicationRejected(409, "Event is not a draft")
        if (
            not event.description.strip()
            or event.start_at.astimezone(UTC) <= now.astimezone(UTC)
            or event.end_at.astimezone(UTC) <= event.start_at.astimezone(UTC)
        ):
            raise PublicationRejected(422, "Publication requires valid future metadata")
        previous = unit.existing_intent(event_id)
        if previous is not None:
            if previous.phase != "prepared":
                raise PublicationRejected(409, "Publication already in progress")
            unit.commit()
            return previous
        intent = PublicationIntent(
            command_id=uuid4(), event_id=event_id,
            event_revision=unit.event_revision(event_id) + 1,
            phase="prepared",
        )
        unit.persist_intent(intent)
        unit.commit()
        return intent
    except Exception:
        unit.rollback()
        raise


def record_closed_gate_snapshot(
    unit: PublicationUnitOfWork,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    gate: SaleGateState,
) -> PublicationIntent:
    """Persist the CAS version observed from Ticketing, still without opening.

    The caller obtains the gate via the authenticated Ticketing read port.
    Persist the version *after* the remote call in a fresh Events transaction;
    never hold Events row locks across an HTTP request. If the gate changes
    later, Ticketing's expected_version check rejects a stale open.
    """
    try:
        event = unit.lock_event(event_id)
        if event is None:
            raise PublicationRejected(404, "Event not found")
        if actor_role not in {"event_owner", "administrator"}:
            raise PublicationRejected(403, "Event owner role required")
        if actor_role != "administrator" and actor_id != event.owner_id:
            raise PublicationRejected(403, "Resource belongs to another user")
        if event.status != "draft":
            raise PublicationRejected(409, "Event is not a draft")
        intent = unit.existing_intent(event_id)
        if intent is None or intent.phase != "prepared":
            raise PublicationRejected(409, "Publication preparation required")
        if (
            intent.event_revision != unit.event_revision(event_id) + 1
            or gate.event_id != event_id
            or gate.state != "closed"
            or gate.version < 0
            or gate.event_revision < 0
            or gate.event_revision >= intent.event_revision
        ):
            raise PublicationRejected(409, "Ticketing gate snapshot not suitable")
        if intent.expected_gate_version is not None:
            if intent.expected_gate_version != gate.version:
                raise PublicationRejected(409, "Gate version changed; reconcile first")
            unit.commit()
            return intent
        unit.bind_gate_version(event_id, gate.version)
        unit.commit()
        return PublicationIntent(
            intent.command_id, intent.event_id, intent.event_revision,
            intent.phase, gate.version,
        )
    except Exception:
        unit.rollback()
        raise
