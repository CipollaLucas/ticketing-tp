## Why

The original system still owns users and sessions in its database, and Orders/Events refer to User UUIDs through foreign keys. A blind Identity cutover would break existing purchases and ownership records.

## What changes

- Introduce an explicit one-time offline user backfill utility in the independent Identity service.
- Default to **dry-run**, listing counts and UUID/username collisions with a source fingerprint.
- Require `--apply --expect-fingerprint <prior snapshot>` before any write.
- Copy users retaining UUID, role, display name, username and existing Argon2 password hash; never copy session tokens.
- Detect changed source snapshots and conflicting existing Identity accounts; reject the entire import without partial writes.
- Run new unit tests of import, dry-run, idempotency, collisions and no sessions copied.

## Out of scope

No automatic production cutover. No removal of legacy user table, auth dependency, foreign keys, or changed React endpoints. A maintenance window, backup and tested rollout/rollback are required before using the import against valuable data.
