# Backup/restore verification for Identity migration

The script `scripts/verify_identity_db_backups.py` is executed on a developer machine that has Docker Desktop and Python 3.12. It locates already-running DB containers using Compose, obtains POSTGRES_USER and POSTGRES_DB from inside each container, and executes pg_dump to a private local binary file **using Python binary streams** (PowerShell redirection is intentionally avoided).

Each archive is restored to a new, uniquely named `postgres:16-alpine` container launched with `--network none`, no host ports and ephemeral storage. This container cannot connect to the original DB, and is removed by `docker stop` after verification, including on failure.

Validation consists of:
- A successful pg_dump custom-format archive with SHA-256 digest.
- A successful pg_restore --exit-on-error to the isolated target database.
- Comparison of row counts for users/sessions/events/orders in legacy and users/sessions in Identity.
- Private manifest including archive filenames, hashes and counts; no password or token values.

The source containers are only queried and backed up, never restored to. Source row counts may change during a busy write workload, in which case the verification must **fail closed**, retain archives and be retried in a quiet window. Counts are a smoke check, not a full semantic equivalence proof; the PostgreSQL archive restore itself is the recovery criterion.

No `--apply` is exposed by this tool. Cutover remains explicitly separate.
