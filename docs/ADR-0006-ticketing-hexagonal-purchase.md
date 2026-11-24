# ADR-0006 — Hexagonal purchase pipeline with transactional UoW

State: implemented in PR for Issue #31, pending CI and merge.

A purchase enters via FastAPI/Pydantic, is converted to a pure PurchaseIntent, passes through the purchase_tickets application use case and the PurchaseUnitOfWorkPort, and is persisted through SqlAlchemyPurchaseUnitOfWork.

The application does not depend on FastAPI or SQLAlchemy and returns an immutable receipt snapshot. The outbound adapter controls row locks, order creation, stock, tickets and PostgreSQL COMMIT/ROLLBACK. Replays return the previous order, not a new allocation. The existing HTTP contract is preserved.

The approach uses **Ports and Adapters (hexagonal)** and **Unit of Work**, plus a domain-level idempotency policy. This is the Ticketing **purchase slice**, not proof that Identity, Events, inventory configuration, or the overall deployment are already hexagonal/microservices. For the full migration refer to ADR-0005.
