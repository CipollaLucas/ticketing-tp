"""Framework-independent Ticketing query use cases."""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.ticketing_core.application.ports import OrderRecord, TicketRecord


@dataclass(frozen=True)
class TicketResultPage:
    items: tuple[TicketRecord, ...]
    total: int
    limit: int
    offset: int


class TicketQueriesPort(Protocol):
    def get_order(self, order_id: UUID, actor_id: UUID) -> OrderRecord: ...
    def my_tickets(self, actor_id: UUID, limit: int, offset: int) -> TicketResultPage: ...


def get_order(order_id: UUID, actor_id: UUID, port: TicketQueriesPort) -> OrderRecord:
    return port.get_order(order_id, actor_id)


def get_my_tickets(
    actor_id: UUID, limit: int, offset: int, port: TicketQueriesPort,
) -> TicketResultPage:
    return port.my_tickets(actor_id, limit, offset)
