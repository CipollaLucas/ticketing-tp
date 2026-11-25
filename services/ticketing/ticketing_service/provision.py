"""Idempotent, *closed-only* gate registration from a trusted Events service.

The caller must have verified that the event UUID exists and is an authorized,
committed Events record. There is deliberately no open operation in this use case.
"""
from typing import Protocol
from uuid import UUID

from ticketing_service.domain import GateConflict, GateState


class GateProvisionUnitOfWork(Protocol):
    def ensure_closed_gate(self, event_id: UUID) -> GateState: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def provision_closed_gate(event_id: UUID, unit: GateProvisionUnitOfWork) -> GateState:
    """Duplicate calls never overwrite an existing open/closed state or version."""
    try:
        state = unit.ensure_closed_gate(event_id)
        unit.commit()
        return state
    except Exception:
        unit.rollback()
        raise


def validate_provision_state(state: GateState, event_id: UUID) -> None:
    if state.event_id != event_id or state.version < 0 or state.event_revision < 0:
        raise GateConflict("Inconsistent existing gate")
