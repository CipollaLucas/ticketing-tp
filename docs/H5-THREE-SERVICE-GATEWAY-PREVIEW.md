# H5 — Three-service Gateway preview (not cutover)

This isolated NGINX entrypoint routes actual browser-facing Stage I *currently extracted* paths to Identity, Events and Ticketing. Its existence does not prove frontend Stage I parity, payment capture, HTTP audits at every service, or operational cutover readiness. Legacy is **never** a fallback.

## Safe local execution

Use a unique disposable Compose project, and only these three overlays (do **not** include the normal docker-compose.yml, legacy volumes or the persistent preview overlays):

```powershell
$env:H3_INTERNAL_TOKEN = "<random 32+ character secret>"
$env:H4_SALES_TOKEN = "<different random 32+ character secret>"
$env:H3_TEST_PASSWORD = "<random disposable test password>"
$files = @("-f", "docker-compose.h3-contract.yml", "-f", "docker-compose.h4-live.yml", "-f", "docker-compose.h5-gateway-preview.yml")
docker compose -p h5-gateway-uat @files config
docker compose -p h5-gateway-uat @files up -d --build h5-gateway
docker compose -p h5-gateway-uat @files exec -T h3-identity alembic upgrade head
docker compose -p h5-gateway-uat @files exec -T h3-events alembic upgrade head
docker compose -p h5-gateway-uat @files exec -T h4-ticketing alembic upgrade head
curl.exe -i http://127.0.0.1:8091/health
curl.exe -i http://127.0.0.1:8091/api/v1/internal/sales/availability
python scripts/h5_gateway_contract_check.py
```

The `up` operation requires service health checks to pass; migrations may be required before apps can become healthy depending on the current DB initialization. If so, start databases first, apply their migrations via one-shot Compose run on the same isolated project, then start the Gateway. Never resolve such issues by stopping another active Compose project.

Do not use `down -v` against any non-disposable project. Only this dedicated test stack uses tmpfs PostgreSQL. Real UAT and port conflicts must be checked separately; port 8091 binds loopback only.

## Explicit browser route matrix

| Public path | Owner | Status |
| --- | --- | --- |
| /api/v1/auth/* | Identity | proxied |
| /api/v1/users/*, /api/v1/admin/users/* | Identity | proxied |
| /api/v1/owner/events* | Events | proxied |
| /api/v1/events (GET/POST) and /api/v1/events/{id} (GET/PATCH) | Events | proxied |
| /api/v1/events/{id}/publish or /unpublish | Events | proxied, flagged off outside UAT |
| /api/v1/events/{id}/orders | Ticketing | proxied, flagged off outside UAT |
| /api/v1/internal/* | none | 404, never public |
| Other /api/* (inventory, my tickets not yet extracted) | none | 503, no Legacy fallback |

## Known blockers for final H5

The current independent Ticketing API exposes purchases, but the existing inventory query and ticket listing browser contracts are not available from this service. Full React Stage I UAT is therefore **not** yet achieved. Extend the contracts in separate reviewed implementation changes before redirecting React. This preview must not activate production purchase gates or payments.

Gateway logs include request ID, method, path, response status, NGINX request_time seconds and upstream response time. These are preliminary gateway records, not evidence that *all services* capture HTTP audit timings. Validate full end-to-end correlation in a later change.
