"""Offline H5 abort decision guard: NEVER changes live routing or databases.

This is deliberately a pure decision model, not an operator cutover tool.
"""
from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    SAFE_PREWRITE_ABORT = "SAFE_PREWRITE_ABORT"
    BLOCK_UNRECONCILED_POSTWRITE_ABORT = "BLOCK_UNRECONCILED_POSTWRITE_ABORT"
    RECONCILIATION_REVIEW_REQUIRED = "RECONCILIATION_REVIEW_REQUIRED"


@dataclass(frozen=True)
class Reconciliation:
    new_confirmed_ticket_ids: frozenset[str]
    legacy_known_ticket_ids: frozenset[str]
    new_writes_frozen: bool
    verified_single_writer: bool

    @property
    def unmatched_ticket_ids(self) -> frozenset[str]:
        return self.new_confirmed_ticket_ids - self.legacy_known_ticket_ids


def decide_abort(state: Reconciliation) -> Decision:
    """Fail closed: never grant automatic return to Legacy after new writes.

    Synthetic evidence of matching records does NOT establish safe production
    rollback: human approval and external reconciliations would still be needed.
    """
    if not state.new_confirmed_ticket_ids:
        return Decision.SAFE_PREWRITE_ABORT
    if (
        not state.new_writes_frozen
        or not state.verified_single_writer
        or state.unmatched_ticket_ids
    ):
        return Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT
    return Decision.RECONCILIATION_REVIEW_REQUIRED
