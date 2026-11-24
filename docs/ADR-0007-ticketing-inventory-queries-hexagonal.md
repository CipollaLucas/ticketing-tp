# ADR-0007 — Hexagonal configuration and query side of Ticketing

Status: Proposed implementation pending CI.

Inventory configuration uses an application use case and InventoryPort. SQLAlchemyInventoryAdapter retains the database row lock on the owning Event, authorization rechecks, PostgreSQL constraints, and transaction commit/rollback. Inventory reads use immutable views independent of ORM models. Orders and tickets use a TicketQueriesPort with SQLAlchemyTicketQueries as an outbound adapter.

Together with ADR-0006 (purchase), this moves Ticketing API operations through application ports. Authorization still relies on shared in-process Identity/Events entities. **This is not yet three microservices**: the next increments must isolate databases, APIs, service-to-service identity/state communication, and verify race safety.

Preserve all existing external API paths and use the current PostgreSQL regression suite as the validation gate.
