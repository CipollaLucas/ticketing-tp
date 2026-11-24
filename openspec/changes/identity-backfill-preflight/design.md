# Identity backfill strategy

This is an **offline administrative migration tool**, not a runtime cross-service data connection. It is located in the Identity service, reads legacy `users` through a separate one-use connection and writes exclusively to the Identity database.

## Safety by default

- Without `--apply`, no writes occur.
- `--apply` is rejected unless a matching prior dry-run SHA-256 fingerprint is supplied.
- The fingerprint covers UUID, username, display name, Argon2 password hash and role without printing password hashes.
- The source is read under repeatable-read isolation on PostgreSQL and each target backfill is one transaction.
- Any conflicting UUID/username, unknown role, failed constraint or changed fingerprint prevents writes; existing Identity identities are **never overwritten**.
- The tool never imports auth_sessions, so sessions must be re-established at a later cutover.

## Before actual use

1. Record separate backups of legacy and Identity databases; test restore.
2. Freeze role/profile modifications during snapshot and import to prevent drift.
3. Dry-run, resolve all collisions, review counts and obtain explicit approval.
4. Apply with matching fingerprint, verify IDs and roles against both databases.
5. Do **not** enable remote authorization until schemas and business IDs are consistent and their legacy foreign keys are removed safely in a distinct migration.

The existing backend continues using its old authentication. This change is necessary preparation, not microservice cutover.
