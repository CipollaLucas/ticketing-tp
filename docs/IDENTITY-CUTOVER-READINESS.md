# Identity cutover readiness: read-only check

The 24/11/2026 local backfill preflight reported **source 4, pending 4, unchanged 0, conflicts 0, applied False**. This is favorable but **no users were transferred**. The current React login, Events and Ticketing use legacy user rows and sessions.

## Run only the read-only audit

Update main and keep the original Docker volumes:

```powershell
git switch main
git pull --ff-only origin main
docker compose -f docker-compose.yml -f docker-compose.identity.yml --profile identity up -d --build identity

docker compose -f docker-compose.yml -f docker-compose.identity.yml --profile identity exec `
  -e LEGACY_DATABASE_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing `
  identity python -m identity.cutover_readiness
```

Expected **before importing**: `Missing accounts: 4`; referenced owner/customer counts depend on existing local events/orders. The command must end with `NOT READY` and **never writes**.

## Before an eventual import

1. Verify independent backups and successful restore of **both** PostgreSQL databases. Do not use `docker compose down -v`.
2. Freeze user/role/profile modifications during snapshot/apply.
3. Re-run `python -m identity.backfill` (dry-run), review conflicts and fingerprint. Do not reuse an old fingerprint blindly.
4. Only with explicit team approval, run a one-time import with `--apply --expect-fingerprint` from that current dry-run.
5. Re-run this readiness check. The audit should find zero missing users and zero mismatches; check every existing owner/customer UUID. No session is transferred, so users must reauthenticate when runtime auth eventually moves.
6. Keep legacy login and foreign keys until a **separate PR** switches authentication and enforces sales/role safety across process boundaries, with rollback tests and a manual UAT.

Even a green readiness check is **not proof** that microservice cutover is completed. Do not publish the internal service token or database credentials.
