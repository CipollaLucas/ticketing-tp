# ADR-0009 — External owner and customer UUID references

Status: Implementation awaiting CI. Local database rollout requires operator approval.

Identity is the future source of truth for user accounts. The next schema-level prerequisite is removing the Legacy users FK constraints from events.owner_id and orders.customer_id, retaining their UUID values and unique/index constraints.

The users and auth_sessions tables remain in the legacy database; currently logged-in Legacy sessions are not copied or revoked. The existing FastAPI authorization stays unchanged.

A reversible Alembic 0005 migration handles PostgreSQL and SQLite. Downgrade recreates local foreign keys only when all values refer to local users.

**Important:** this is not a remote authentication cutover. Removing an FK no longer lets PostgreSQL reject an arbitrary external UUID. Protected writes must verify current Identity roles even after row lock waits before they can accept remote tokens. That separate change requires fail-closed tests and an explicit UAT.

Before local DDL: verify fresh backups of both databases and successful restore; review current IDs and avoid concurrent changes. Never remove Legacy users or auth_sessions in this step.
