# Preflight: legacy users to independent Identity

**Status: preparation, not an authorization cutover.**

The original system still uses its own user and session tables for React, Events, Orders and Ticketing. The independent Identity Service has a different database and may contain unrelated demo accounts. This migration cannot simply swap the auth URL: it must preserve the original user UUIDs referenced by Events and Orders.

The `identity.backfill` utility is an **offline administrative migration**, and is intentionally not part of normal request handling. It does not import sessions; new logins will be required when the full cutover eventually occurs.

## Safe inspection, no writes

On Windows PowerShell, with the same `IDENTITY_INTERNAL_TOKEN` used to run the Identity overlay:

```powershell
$compose = @('-f', 'docker-compose.yml', '-f', 'docker-compose.identity.yml', '--profile', 'identity')
docker compose @compose exec identity python -m identity.backfill --help
```

A real dry-run needs `LEGACY_DATABASE_URL` supplied **only to that one process**. The existing backend development database is accessed through the Docker network at `db:5432`; Identity's `DATABASE_URL` already points to `identity-db`.

```powershell
docker compose @compose exec -e LEGACY_DATABASE_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing identity python -m identity.backfill
```

The dry-run prints source, pending, unchanged, conflicts, and a source fingerprint. It changes **neither** database.

**Do not run an apply yet.** The local preview Identity database may already include users created while testing Swagger, and collisions must be reviewed. Before an eventual write: verify backups and restore, freeze user/role mutations, inspect the dry-run, verify account IDs and obtain team approval. Only then would an operator intentionally run:

```text
python -m identity.backfill --apply --expect-fingerprint <fingerprint-from-dry-run>
```

Never paste real credentials, tokens or password hashes into chat or the repository. Never run `docker compose down -v`. The role/ownership references and database foreign keys in the original backend remain unchanged until a separate, tested schema and auth cutover.
