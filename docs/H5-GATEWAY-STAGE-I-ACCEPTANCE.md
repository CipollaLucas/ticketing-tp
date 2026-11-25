# H5 Stage I acceptance through Gateway — CI evidence plan

OpenSpec change: `h5-gateway-stage-i-cutover` (implement phase). This increment creates a **real HTTP** three-service UAT through NGINX, with no Legacy container.

## Execution and isolation

CI job `h5-gateway-stage-i` combines `docker-compose.h3-contract.yml`, `docker-compose.h4-live.yml` and `docker-compose.h5-gateway-preview.yml` under unique project `h5-gateway-ci`. It builds images, starts three independent PostgreSQL 16 databases using tmpfs, runs independent Alembic migrations, seeds two disposable Identity accounts, starts services and NGINX, and invokes `h5-gateway-smoke`.

The smoke runner refuses non-`h4_ticketing_test` databases, requires `H5_DISPOSABLE_UAT=yes`, and accepts only `http://h5-gateway:8080` as its HTTP target. All domain HTTP requests go through the Gateway; it does not call Identity, Events or Ticketing URLs directly. The standalone H4 suite separately covers PostgreSQL concurrency races.

## Scenarios tested

1. Gateway health; block private `/api/v1/internal/*`; unknown API paths fail closed.
2. Owner/customer logins, authenticated user lookup, missing bearer.
3. Owner creates draft; public catalog cannot expose it.
4. Owner creates an ordinary general-admission zone; customer cannot configure zones.
5. Owner publishes; catalog and public event become visible.
6. Public inventory reports two available tickets.
7. Customer buys with React `POST /api/v1/orders` and an idempotency key: one confirmed order, one ticket, capacity decremented once.
8. Same-key retry returns 200, same order/ticket and replay header. Reusing key with different body returns 409.
9. Customer `/api/v1/me/tickets` shows their ticket; owner cannot read customer tickets.
10. Unpublish is refused with 409 after confirmed purchase; logout invalidates customer session.

## Not claimed by this PR

- This is an **API client simulation**, not a real browser-driven React Playwright journey.
- No administrator journey is exercised (the isolated H3 seed only creates owner/customer).
- The known publish-vs-zone-configuration TOCTOU race remains to be resolved with a coordinated protocol.
- Full per-service HTTP audit/latency logging, restart/restore scenarios and safe production rollback remain separate H5 gates.
- A confirmed simulated ticket is an allocated ticket, **not** proof of captured payment.

Do not archive the H5 OpenSpec change or activate production cutover based only on this job. Record exact green CI run and continue with the unresolved gates.

## Proposed H5 three-role expansion

The H5 overlay now opts into an administrator seed using a separate script guarded by the disposable `h3_identity_test` database, the H3 seed flag and an H5-specific flag. The H3 two-user seed remains unchanged, so existing H3/H4 test suites are not altered. The new smoke authenticates the administrator through Gateway, verifies admin role, demonstrates owner/customer cannot modify another user's role, demonstrates administrator can perform a role-management request without changing the customer's role, and verifies the administrator can list managed events while the customer cannot.

This proves **HTTP three-role API authorization**, not a real React browser journey. The preceding 'No administrator journey' limitation refers to the previous two-user test; it is superseded only after the new CI job has passed. Separate administrator browser UAT and real data cutover approval remain outstanding.
