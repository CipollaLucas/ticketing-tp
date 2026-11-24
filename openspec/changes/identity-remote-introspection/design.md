# Remote Identity contract

Application: `AuthenticatedPrincipal`, `IdentityPort`, `IdentityUnauthorized` and `IdentityUnavailable`, independent of HTTP and SQLAlchemy.

Adapter: `HttpIdentityAdapter` sends `GET /api/v1/internal/auth/introspect` with the user's Bearer token and server-only `X-Internal-Service-Token`. The URL and secret are supplied through environment in an opt-in Docker Compose overlay. Strict Pydantic response parsing occurs **outside** the application.

- 200 with a valid, known role: return principal snapshot.
- 401: unauthenticated.
- 403, 404, 429, 5xx, malformed response or network timeout: fail closed as IdentityUnavailable.
- Never fall back to local user tables, never silently accept stale roles.
- No redirects, ambient proxy discovery or secret-bearing logs.
- Each lookup performs a fresh remote call; no TTL role cache until revocation semantics are formally designed.

Integration smoke: start Identity and its private PostgreSQL, apply its Alembic migration, create a random test user over HTTP, login, introspect from backend container, logout, then require a 401 for the same token. This proves token revocation between processes.

**Safety boundary:** no existing endpoint uses this adapter for authorization in this PR, because the original Event.owner_id and Order.customer_id still have foreign keys to legacy User. The migration of ownership and identity must precede the cutover.
