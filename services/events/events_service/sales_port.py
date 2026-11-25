"""Pure Events outbound contract for Ticketing sale gates.

Event publication is NOT exposed by this module. Status alone cannot safely
authorize publish/unpublish without a durable coordination protocol.
"""
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class SaleGateState:
    event_id: UUID
    state: Literal["open", "closed"]
    version: int
    event_revision: int


@dataclass(frozen=True)
class SaleGateCommand:
    event_id: UUID
    command_id: UUID
    action: Literal["open", "close"]
    expected_version: int
    event_revision: int


class SaleGateUnavailable(Exception):
    """Uncertain remote result: never assume opening or closing succeeded."""


class SaleGateRejected(Exception):
    """Authenticated Ticketing server rejected a command or protocol payload."""


class SaleGatePort(Protocol):
    def state(self, event_id: UUID, request_id: str | None = None) -> SaleGateState: ...
    def command(
        self, value: SaleGateCommand, request_id: str | None = None,
    ) -> SaleGateState: ...
    def close_without_sales(
        self, value: SaleGateCommand, request_id: str | None = None,
    ) -> SaleGateState: ...


def verified_gate_state(
    port: SaleGatePort, event_id: UUID, request_id: str | None = None,
) -> SaleGateState:
    """Read only. Unknown gate stays closed; caller cannot publish from it."""
    return port.state(event_id, request_id)
