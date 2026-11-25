# H5 — Identity-only Gateway preview (Stage I vertical parity)

This slice proves **the real browser-facing /api/v1/auth/** contract through a reverse proxy to the independent Identity HTTP service, with its own PostgreSQL. It does **NOT** switch React or activate full microservices yet.

The gateway is a separate NGINX container, exposed only on `127.0.0.1:8090`, while React continues its existing Vite proxy to the original Legacy backend at `127.0.0.1:8000`. Gateway forwards `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/admin/users/*` to Identity, never to Legacy. Other `/api/*` routes return 503. This is essential: an Identity-issued session is not accepted by Legacy business routes; falling back would create inconsistent user sessions.

## Run isolated UAT without modifying active Compose volumes

Use the separate project name `h5-identity-uat` so `identity-db` cannot reuse `ticketing-tp` volumes. Choose a **unique** 32+ character service token. Keep it out of git, terminal logs, screenshots and client JavaScript. The run requires Docker and no other application binding `127.0.0.1:8001` or `127.0.0.1:8090`. If ports are occupied by a previous Identity preview, use CI results instead; **do not stop or remove existing containers** to clear them.

```powershell
$env:IDENTITY_INTERNAL_TOKEN = "<supply-a-unique-secret-at-least-32-characters>"
$compose = @(
  "-p", "h5-identity-uat",
  "-f", "docker-compose.yml",
  "-f", "docker-compose.identity.yml",
  "-f", "docker-compose.identity-gateway-preview.yml"
)
docker compose @compose --profile identity --profile identity-gateway-preview up -d --build identity-gateway-preview
docker compose @compose --profile identity exec -T identity alembic upgrade head
python scripts/identity_gateway_preview_smoke.py
```

**Note:** Compose dependencies may start Identity DB/Identity and the backend depending on configuration; isolated project naming keeps their volumes independent. CI runs the smoke test using dedicated ephemeral GitHub runner containers. The smoke creates only a disposable customer, checks login/current-user/logout/revocation and confirms Events returns 503 (never falls through to Legacy).

For rollback simply **stop invoking** this preview; React is never redirected. Never run `docker compose down -v` or `--remove-orphans` on the active project. No data migration and no user cutover happen here.

## Acceptance and next gate
- [ ] NGINX config and Compose build/boot, health 200.
- [ ] Remote Identity registers, logs in, returns profile with the original schema and revokes token after logout.
- [ ] Events and other commercial routes are **unavailable** through preview (503), not routed to Legacy.
- [ ] CI backend/Identity/Events/Ticketing/React unchanged and green.
- [ ] Full H5 later: real business-route mapping and a whole Stage I React flow with Legacy stopped, followed by a tested rollback and cutover plan.
