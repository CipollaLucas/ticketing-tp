## Why
Local cutover readiness reported 4 missing legacy users and 2 referenced UUIDs missing from standalone Identity. Backfill must not occur without verified recovery copies of *both* active PostgreSQL databases.

## What changes
- Introduce a host-side, Python standard-library-only workflow that uses Docker CLI to dump legacy and Identity DBs separately in PostgreSQL custom format.
- Verify each dump by starting a disposable PostgreSQL 16 container with networking disabled and restoring it using pg_restore --exit-on-error.
- Compare counts of critical tables (legacy users/sessions/events/orders; Identity users/sessions), calculate SHA-256 hashes and produce a local manifest.
- Avoid any pg_restore or DDL against original databases; never stop/remove source volumes.
- Ignore backups and manifest directory from Git and add CI smoke that proves the restore procedure using disposable databases.

## Out of scope
No user backfill --apply, migration of foreign keys, login cutover or service data transfer.
