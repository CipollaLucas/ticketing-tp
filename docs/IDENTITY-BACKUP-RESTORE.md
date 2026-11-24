# Identity migration — verified backups of both PostgreSQL databases

**Objective:** recoverable snapshots of the active legacy and Identity DBs before any backfill, schema migration or authentication cutover.

The last local audit returned: **4 legacy users, 1 Identity user, 2 referenced legacy UUIDs, 4 missing accounts, 2 unresolved references, 16 legacy sessions**. All data remains unchanged. The workflow below **does not import or alter** those identities.

## Run on Windows PowerShell (Docker Desktop + Python 3.12)

Keep the running Compose databases and their volumes. If using the Identity overlay, set the same `IDENTITY_INTERNAL_TOKEN` in your current PowerShell session, although the backup tool never uses it to authenticate to PostgreSQL.

```powershell
git switch main
git pull --ff-only origin main

python scripts/verify_identity_db_backups.py
```

The command saves unique `.dump` files and a local JSON verification manifest under `backups/verified/`, excluded from Git. It runs pg_dump against **both live DBs**, then restores each into a *new, offline and disposable* PostgreSQL container, verifies key table counts and removes each temporary container. No `docker compose down -v`, volume deletion, source DDL or source pg_restore is performed.

A successful run ends with:

```text
RESTORE legacy: PASS, isolated and offline, counts=...
RESTORE identity: PASS, isolated and offline, counts=...
PASS: both restored independently. Manifest: ...
No source volumes, schemas, users or sessions were modified.
```

The script returns nonzero on any missing DB container, dump failure, pg_restore failure, wrong counts or bad checksum. It retains the files to support diagnosis. A failed run **is not** evidence that a database restore was verified.

For another private storage location:

```powershell
python scripts/verify_identity_db_backups.py --output-dir "D:\\Resguardos\\ticketing-tp"
```

## Required review before any Identity import

1. Confirm both `.dump` files and manifest exist, hashes match and both restores passed. Keep archives securely outside the source-control repository for retention.
2. Review any source writes during the backup. The row count comparison is conservative; if data changes during the snapshot, repeat in a quiet window.
3. Verify a backup/restore procedure for real recovery and retain the original backup files until cutover is accepted.
4. Re-run `identity.backfill` **dry-run** (fingerprint must be current), resolve all conflicts, and obtain explicit team approval before any apply.
5. After importing users, rerun `identity.cutover_readiness`. Do not treat its pass as proof that Events/Orders no longer depend on legacy `users`.
6. Plan a separate tested schema/authorization cutover with rollback. Never copy legacy Bearer sessions.

**Important:** backups include password hashes and potentially personal data. Protect access, avoid posting them to GitHub or chats, and never share the archives publicly.
