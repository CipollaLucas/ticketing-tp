# H5 Gateway architecture and acceptance design

## Routing and ownership

NGINX (or equivalent lightweight reverse proxy) is the only browser entry for /api/v1. It forwards paths to Identity, Events or Ticketing according to exact documented public contracts. Resolve overlapping /events paths by method/path-aware routing or explicit route partition; do not route purchases and event metadata to the wrong owner. Generate and validate a routing matrix against service OpenAPI specs before any implementation. Internal endpoints must not be exposed via the public gateway. Unknown routes fail closed (404/503), never proxy to Legacy.

Identity owns /auth, /users and /admin/users. Events owns event metadata and publication. Ticketing owns inventory, zones, orders and issued tickets. Confirm actual path shapes and prefix precedence from code and OpenAPI; these are ownership rules, not a claim of complete configured routes.

## Identity and safety

Forward Authorization and X-Request-ID to the correct service; service-to-service secrets never reach browser configuration. A request accepted by Identity must not route to Legacy. Gateway fail-closed on unavailable backend; protected writes require service-side verification, bounded timeouts and explicit error mapping.

## Evidence plan

Use Docker Compose project name unique to H5 with independent ephemeral PostgreSQL instances; no shared active volumes. Boot services and Gateway, run Alembic migrations, execute client-like HTTP flows and React e2e through the Gateway while Legacy is intentionally unavailable. Prove login/logout/revocation, role access, draft/edit/publish/unpublish, catalog, inventory, customer purchase and idempotent retry; run concurrent last-stock and purchase-vs-close races. Ensure no accidental payment claim: confirmed tickets mean allocated, not paid.

Inject fault modes separately: backend unavailability, lost ACK after commit, repeated command_id, restart during recovery and preserved state on PostgreSQL restore. Track actual scenarios rather than asserting complete coverage based on one 503 proxy simulation.

## Rollout / rollback

Separate preview Compose/config from any deployable cutover config. Default cutover OFF; only after review can a deliberate switch point React to full Gateway. Backup and restore of each database verified, migration/backfill with zero missing referenced IDs, and no cross-service foreign keys. Rollback must account for new writes (do not blindly point clients back at stale Legacy tables). Prefer disabling new writes and restoring to an agreed safe state over unsafe dual-writing. Explicit signoff required.

## Observability

End-to-end X-Request-ID correlation and structured HTTP access records per request: timestamp, service, method, route, status, duration_ms (monotonic clock), correlation id and error category. Include authorized and rejected requests; do not log passwords, Authorization, cookies, service tokens or payload secrets. Verify each hop includes time and outcome. Document limitations and overhead.

## Decision gates

1. Routing contract verified against current APIs.
2. Separate databases + service readiness green.
3. H4 invariants and failures reproduced through gateway.
4. React Stage I complete with Legacy off.
5. Audit logs trace successful and failed requests without secrets.
6. Reversible operational plan and team approval before any real cutover.

No merging a proposal is interpreted as satisfaction of these gates.
