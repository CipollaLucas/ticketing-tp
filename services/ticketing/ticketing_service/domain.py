"""Pure sale gate rules; no HTTP or persistence dependencies."""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

SaleState = Literal["closed", "open"]


class GateConflict(ValueError):
    """Stale, invalid or conflicting sale-state command."""


@dataclass(frozen=True)
class GateState:
    event_id: UUID
    state: SaleState
    version: int
    event_revision: int


@dataclass(frozen=True)
class GateCommand:
    command_id: UUID
    event_id: UUID
    action: Literal["open", "close"]
    expected_version: int
    event_revision: int


def next_gate(current: GateState, command: GateCommand) -> GateState:
    if current.event_id != command.event_id:
        raise GateConflict("Wrong event")
    if current.version != command.expected_version:
        raise GateConflict("Stale sale gate version")
    if command.event_revision < current.event_revision:
        raise GateConflict("Stale metadata revision")
    if command.expected_version < 0 or command.event_revision < 0:
        raise GateConflict("Invalid version")
    if command.action == "open" and command.event_revision <= current.event_revision:
        raise GateConflict("Opening requires a newer published metadata revision")
    if command.action not in {"open", "close"}:
        raise GateConflict("Unknown command")
    desired: SaleState = "open" if command.action == "open" else "closed"
    if desired == current.state:
        raise GateConflict("Redundant command requires reconciliation")
    return GateState(
        event_id=current.event_id,
        state=desired,
        version=current.version + 1,
        event_revision=command.event_revision,
    )
