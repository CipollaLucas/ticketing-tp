"""Sale gate use cases and transaction port.

This is not yet the purchase use case. The future purchase operation MUST use
the exact same gate row lock in its own local SQL transaction.
"""

from typing import Protocol
from uuid import UUID

from ticketing_service.domain import GateCommand, GateConflict, GateState, next_gate


class SaleGateUnitOfWork(Protocol):
    def previous_command(self, command: GateCommand) -> tuple[GateCommand, GateState] | None: ...
    def lock_gate(self, event_id: UUID) -> GateState | None: ...
    def save(self, command: GateCommand, state: GateState) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def change_sale_gate(command: GateCommand, unit: SaleGateUnitOfWork) -> GateState:
    """Idempotency and CAS check share the transaction protecting gate state."""
    try:
        previous = unit.previous_command(command)
        if previous is not None:
            old_command, result = previous
            if old_command != command:
                raise GateConflict("Command ID reused with another payload")
            unit.rollback()  # release transaction / snapshot; no new mutation
            return result
        current = unit.lock_gate(command.event_id)
        if current is None:
            raise GateConflict("Unknown events remain closed")
        # Important: after waiting for a gate lock, re-check command record.
        previous = unit.previous_command(command)
        if previous is not None:
            old_command, result = previous
            if old_command != command:
                raise GateConflict("Command ID reused with another payload")
            unit.rollback()
            return result
        result = next_gate(current, command)
        unit.save(command, result)
        unit.commit()
        return result
    except Exception:
        unit.rollback()
        raise
