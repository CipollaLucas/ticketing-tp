"""Ports for a future standalone Ticketing service.

Interfaces are owned by the application, not by SQLAlchemy or HTTP clients.
Production adapters will implement these while preserving the PostgreSQL lock
order and atomic order/ticket creation.
"""
from typing import Protocol
from uuid import UUID

from app.ticketing_core.domain.purchase import PurchaseIntent


class EventSalesPort(Protocol):
    def is_sale_open(self, event_id: UUID) -> bool:
        """Consult the authoritative event state without importing Events models."""
        ...


class PurchaseUnitOfWorkPort(Protocol):
    def lock_customer(self, customer_id: UUID) -> None:
        """Serialize per-customer idempotency before a purchase."""
        ...

    def allocate(self, customer_id: UUID, key: str, intent: PurchaseIntent) -> UUID:
        """Atomically create an order and its tickets, or fail."""
        ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
