"""Events-owned, authorized coordinator for idempotent closed-only provisioning.

This never changes Event metadata or opens sales. Identity verification is
performed by the inbound edge at each invocation; Events owns event existence.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from events_service.gate_readiness import GateReadinessReader, verify_gate_candidate
from events_service.sales_port import SaleGateState, SaleGateUnavailable


class ClosedGateProvisionPort(Protocol):
    def provision(self, event_id: UUID, request_id: str | None = None) -> SaleGateState: ...


@dataclass(frozen=True)
class ProvisionOutcome:
    event_id: UUID
    state: SaleGateState


def provision_verified_draft(
    reader: GateReadinessReader,
    remote: ClosedGateProvisionPort,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    now: datetime,
    request_id: str | None = None,
) -> ProvisionOutcome:
    candidate = verify_gate_candidate(reader, event_id, actor_id, actor_role, now)
    result = remote.provision(candidate.event_id, request_id)
    if (
        result.event_id != candidate.event_id
        or result.state not in {"closed", "open"}
        or result.version < 0 or result.event_revision < 0
    ):
        raise SaleGateUnavailable("Ticketing provision confirmation invalid")
    # No assertion that pre-existing gates are closed; never silently close.
    return ProvisionOutcome(candidate.event_id, result)
