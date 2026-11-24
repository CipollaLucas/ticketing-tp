## Why
Identity now independently owns migrated users, but event owner and order customer references still have database foreign keys to Legacy users.

## What changes
- Add a reversible Alembic migration dropping only Legacy users FKs on events.owner_id and orders.customer_id.
- Keep UUID columns, all users/sessions, indexes, orders, inventory and tickets.
- Test PostgreSQL and SQLite upgrade/downgrade, including existing identifiers.

## Non-goals
No live Identity auth cutover and no physical split of Events/Ticketing. Schema rollout requires a separately reviewed backup and operator action.
