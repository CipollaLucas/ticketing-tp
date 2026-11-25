"""Pure verification policy before any future remote gate provisioning.

A legitimate, committed draft event is required; only its owner or a verified
administrator may initiate the eventual coordination protocol.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from events_service.domain import EventRecord


class GateReadinessDenied(Exception):
    """Event is missing, unauthorized, already published or no longer upcoming."""


class GateReadinessReader(Protocol):
    def by_id(self, event_id: UUID) -> EventRecord | None: ...


@dataclass(frozen=True)
class VerifiedGateCandidate:
    event_id: UUID
    owner_id: UUID
    status: str
    start_at: datetime


def verify_gate_candidate(
    reader: GateReadinessReader,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    now: datetime,
) -> VerifiedGateCandidate:
    if actor_role not in {"event_owner", "administrator"}:
        raise GateReadinessDenied("Event not available for this actor")
    event = reader.by_id(event_id)
    if event is None or (
        actor_role != "administrator" and event.owner_id != actor_id
    ):
        # Do not reveal another organizer's event existence.
        raise GateReadinessDenied("Event not available for this actor")
    if event.status != "draft" or event.start_at.astimezone(UTC) <= now.astimezone(UTC):
        raise GateReadinessDenied("Event cannot be prepared for sales")
    return VerifiedGateCandidate(
        event_id=event.id, owner_id=event.owner_id,
        status=event.status, start_at=event.start_at,
    )
