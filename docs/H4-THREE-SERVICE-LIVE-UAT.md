# H4 — Live UAT with three isolated PostgreSQL databases

This is a real HTTP integration test for Identity, Events, and Ticketing using a **dedicated Docker Compose project**, building on the existing H3 contract.

## Safety and scope

The UAT uses `docker-compose.h3-contract.yml` plus `docker-compose.h4-live.yml`. It does **not** use the regular developer Compose deployment. All three PostgreSQL databases use `tmpfs` and have distinct credentials and schemas. There are no mapped host ports or named volumes. The test refuses to run if Events is not connected to `h3_events_test`.

Only these disposable containers are stopped at the end of CI via the dedicated project name `h4-live-ci`. No `down -v`, `--remove-orphans`, database reset, or manipulation of existing local volumes.

## Positive checks

1. Login with an actual Identity event owner and customer.
2. Draft creation by the owner; customer publication returns 403.
3. Publish via Events HTTP. The real Ticketing provision/CAS opens `closed v0/revision 0 -> open v1/revision 1`.
4. Repeated publish is idempotent; public detail is visible.
5. Unpublish via Events HTTP and Ticketing conditional no-sales close, yielding `closed v2/revision 2`. Public detail becomes 404.
6. Repeated unpublish is idempotent.
7. Republish after close produces `open v3/revision 3`; Events and Ticketing revisions agree.
8. No Identity/Event foreign keys across service-owned databases.

## Still required before commercial cutover

- Inject a **confirmed order** through the Ticketing purchase path and verify real HTTP unpublish 409, unchanged metadata and open gate.
- Verify purchase-vs-close contention across separate processes. Ticketing's disposable PostgreSQL unit/integration tests already cover transaction ordering, but this live smoke currently tests the no-sales path.
- Inject network loss after Ticketing's commit, service restart, Identity failure and session revocation during publication/unpublication.
- Run backup/restore and a controlled UAT with representative Legacy records; verify routing and rollback procedures.
- All opt-in feature flags remain default-off in regular compose and runtime; this smoke explicitly turns them on only in the disposable overlay.

## Run manually (PowerShell, isolated)

```powershell
$env:H3_INTERNAL_TOKEN = -join ((1..64) | ForEach-Object { '0123456789abcdef'[(Get-Random -Maximum 16)] })
$env:H4_SALES_TOKEN = -join ((1..64) | ForEach-Object { '0123456789abcdef'[(Get-Random -Maximum 16)] })
$env:H3_TEST_PASSWORD = -join ((1..48) | ForEach-Object { 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'[(Get-Random -Maximum 62)] })
$files = @("-f", "docker-compose.h3-contract.yml", "-f", "docker-compose.h4-live.yml")
$project = "h4-live-manual"

docker compose -p $project @files build h3-identity h3-events h4-ticketing h4-live-smoke
docker compose -p $project @files up -d --wait h3-identity-db h3-events-db h4-ticketing-db
foreach ($service in @("h3-identity", "h3-events", "h4-ticketing")) {
    docker compose -p $project @files run --rm --no-deps $service alembic upgrade head
}
docker compose -p $project @files run --rm --no-deps h3-identity python -m identity.h3_contract_seed
docker compose -p $project @files up -d --wait h3-identity h4-ticketing h3-events
docker compose -p $project @files run --rm --no-deps h4-live-smoke

# Only after confirming that this project contains exclusively disposable UAT containers:
docker compose -p $project @files down
Remove-Item Env:H3_INTERNAL_TOKEN, Env:H4_SALES_TOKEN, Env:H3_TEST_PASSWORD
```

No developer production or ordinary local database credentials are needed.
