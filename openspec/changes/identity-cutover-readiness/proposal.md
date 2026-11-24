## Why

The local offline dry-run found four legacy accounts pending and no username/UUID collisions, but **no import has been applied**. Before any schema change or authorization cutover, we must verify that the Identity database contains every legacy account and every event owner and order customer UUID.

## What changes

- Add a **read-only cross-database cutover audit**, separate from the write-enabled offline backfill tool.
- Compare all legacy user UUIDs and attributes against independent Identity.
- Check all existing Event.owner_id and Order.customer_id references independently of the legacy users table.
- Report counts, snapshot fingerprint and remaining legacy session count without revealing credentials or identities.
- Require explicit manual review after a successful audit: a passing result is NOT permission to remove foreign keys or enable remote auth.

## Out of scope

No automatic import, no Alembic schema mutation, no deletion of legacy tables, no routing changes, no deployment cutover.
