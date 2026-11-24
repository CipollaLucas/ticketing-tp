# H3/H4: Explicit sale-state coordination

## Why

The original Legacy backend stores Event and Order in the same database and locks the event during commercial transitions. H3 Events and future H4 Ticketing will use separate databases. A GET to Events before purchasing and a GET to Ticketing before unpublishing creates a time-of-check/time-of-use race: both could succeed. ADR-0005 explicitly prohibits enabling remote unpublish on that basis.

## Scope

Define an implementable, versioned sale-state contract in which **Ticketing is the only authority that opens/closes sales** and protects order commits using the same local transaction and locks. Events retains exclusive ownership of event metadata and draft/published state. No distributed transaction or cross-database SQL/FK.

This increment is design and acceptance criteria only. It does not activate routes, migrate orders, or allow remote unpublish. H4 must implement and demonstrate the atomic sale gate before H3 enables commercial transitions.

## Compatibility

React stays on Legacy until H5 Gateway cutover. Existing Identity and Events preview services remain opt-in. Purchase idempotency, stock locking, existing tickets, and confirmed purchases are invariant across the migration.
