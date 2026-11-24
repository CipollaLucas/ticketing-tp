# Read-only Identity canary before authentication cutover

**Status: optional diagnostic only.** This does **not** change React login or allow remote-authenticated event creation or purchases.

The independent Identity database now contains the four migrated users. The Legacy DB still holds 16 old sessions and all Event.owner_id and Order.customer_id foreign keys. Do not remove them yet.

## Enable explicitly in local development

Update main after the PR is merged. Set the same internal service credential used for the opt-in Compose overlay and then start backend with the additional environment setting. Avoid publishing the secret in shell transcripts or chat.

```powershell
$env:IDENTITY_CANARY_ENABLED = "true"
docker compose -f docker-compose.yml -f docker-compose.identity.yml --profile identity up -d --build backend identity
```

The Compose overlay must pass `IDENTITY_CANARY_ENABLED` into the backend service. Otherwise it remains off (HTTP 404).

Log into **Identity** Swagger at `http://localhost:8001/docs`, obtain a newly issued Bearer token from a migrated account, and call `GET http://localhost:8000/api/v1/identity/canary` using that token.

- 200: remote Identity token and Legacy UUID/role/username agree. This is read-only.
- 401: missing or revoked token.
- 409: missing local UUID or drift between remote and local role/username.
- 503: Identity unreachable or service credential/response invalid.
- 404: canary disabled.

No successful canary call permits buying tickets. The existing frontend and old sessions keep their original behavior. A later controlled migration must replace all authorization dependencies, recheck roles under transaction locks using the remote authority and remove cross-service DB FKs with proven rollback.
