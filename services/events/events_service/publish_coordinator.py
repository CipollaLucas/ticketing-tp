"""One recoverable Stage I publish orchestration across Events and Ticketing.

No distributed SQL transaction. Metadata is committed before sending the
versioned sale-open command. The same persistent command_id is replayed
after uncertain HTTP outcomes. Caller MUST freshly verify Identity.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from events_service.provisioning import ClosedGateProvisionPort
from events_service.publication import (
    PublicationIntent,
    PublicationRejected,
    PublicationUnitOfWork,
    commit_published_metadata,
    prepare_publication,
    record_closed_gate_snapshot,
)
from events_service.sales_port import (
    SaleGateCommand,
    SaleGatePort,
    SaleGateState,
    SaleGateUnavailable,
)


@dataclass(frozen=True)
class PublishResult:
    intent: PublicationIntent
    gate: SaleGateState


def publish_via_ticketing(
    units: PublicationUnitOfWork,
    provisioner: ClosedGateProvisionPort,
    sales: SaleGatePort,
    event_id: UUID,
    actor_id: UUID,
    actor_role: str,
    now: datetime,
    request_id: str | None = None,
) -> PublishResult:
    """Idempotent orchestration, limited to an authorized event UUID.

    An implementation of units must use fresh local transactions after each
    commit. No Events SQL transaction is held during remote HTTP calls.
    """
    intent = prepare_publication(units, event_id, actor_id, actor_role, now)
    if intent.phase == "prepared":
        if intent.expected_gate_version is None:
            # The provision result proves the gate row exists in Ticketing.
            # GET alone would synthesize "closed" for a missing gate.
            gate = provisioner.provision(event_id, request_id)
            intent = record_closed_gate_snapshot(
                units, event_id, actor_id, actor_role, gate,
            )
        intent = commit_published_metadata(
            units, event_id, actor_id, actor_role, now,
        )
    if intent.phase != "metadata_published" or intent.expected_gate_version is None:
        raise PublicationRejected(409, "Publication command not ready")
    command = SaleGateCommand(
        event_id=event_id,
        command_id=intent.command_id,
        action="open",
        expected_version=intent.expected_gate_version,
        event_revision=intent.event_revision,
    )
    # A timeout here is UNKNOWN, never success. Next invocation reuses exactly
    # the same command and Ticketing's command history returns the prior ACK.
    gate = sales.command(command, request_id)
    if (
        gate.event_id != event_id or gate.state != "open"
        or gate.version != intent.expected_gate_version + 1
        or gate.event_revision != intent.event_revision
    ):
        raise SaleGateUnavailable("Ticketing did not confirm matching opening")
    return PublishResult(intent, gate)
