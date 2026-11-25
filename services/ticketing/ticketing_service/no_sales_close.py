"""Atomic no-sales close of Ticketing's gate, under the purchase row lock.

Legacy refuses unpublish if any confirmed order exists. Checking order count
before the lock would race with a new purchase; both checks must share the
same Ticketing transaction as the sale-gate transition.
"""

from typing import Protocol
from uuid import UUID

from ticketing_service.domain import GateCommand, GateConflict, GateState, next_gate


class ConfirmedSalesExist(GateConflict):
    """Unpublish must be rejected; historical sales must not be erased."""


class CloseWithoutSalesUnit(Protocol):
    def previous_command(self, command: GateCommand) -> tuple[GateCommand, GateState] | None: ...
    def lock_gate(self, event_id: UUID) -> GateState | None: ...
    def confirmed_order_exists(self, event_id: UUID) -> bool: ...
    def save(self, command: GateCommand, state: GateState) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def close_gate_without_sales(
    command: GateCommand,
    unit: CloseWithoutSalesUnit,
) -> GateState:
    """Idempotent CAS close; purchase and close serialize on same gate row.

    A historical replay returns the original command outcome. A *new* close
    must refuse if orders were confirmed before acquiring the gate lock.
    """
    try:
        if command.action != "close":
            raise GateConflict("Only close is allowed by no-sales command")
        previous = unit.previous_command(command)
        if previous is not None:
            old, result = previous
            if old != command:
                raise GateConflict("Command ID reused with another payload")
            unit.rollback()
            return result
        current = unit.lock_gate(command.event_id)
        if current is None:
            raise GateConflict("Unknown events remain closed")
        previous = unit.previous_command(command)
        if previous is not None:
            old, result = previous
            if old != command:
                raise GateConflict("Command ID reused with another payload")
            unit.rollback()
            return result
        if unit.confirmed_order_exists(command.event_id):
            raise ConfirmedSalesExist("Cannot unpublish an event with sales")
        result = next_gate(current, command)
        unit.save(command, result)
        unit.commit()
        return result
    except Exception:
        unit.rollback()
        raise
