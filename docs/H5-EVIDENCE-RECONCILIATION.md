# H5 — Acceptance evidence reconciliation

OpenSpec `h5-gateway-stage-i-cutover`. This register is a review aid, not authorization to deploy.

| Evidence | Merged PR | Scope |
| --- | --- | --- |
| Three-service isolated Gateway | #84 | no Legacy fallback in disposable UAT |
| Public inventory | #85 | Ticketing-owned reads |
| Customer tickets | #86 | Identity-protected own-ticket listing |
| Zones and publication serialization | #87, #92 | local gate-row concurrency |
| React purchase compatibility | #89 | idempotent Ticketing order transaction |
| End-to-end Gateway HTTP UAT | #90 | event, zone, purchase, replay, security |
| HTTP audit and four-process correlation | #91, #93 | request IDs and timings |
| Three-role HTTP tests | #94 | administrator, owner, customer |
| Real Chromium React | #95 | browser journey without Legacy |
| Restart/replay | #96 | persistence across app process restart |
| Three PostgreSQL restores | #97 | SHA-256, isolated pg_restore and count comparisons |
| Ruff formatting baseline | #88 | maintenance only |

All PRs above were reported merged with green CI. **Exact CI run URLs, SHAs and approval record must be attached before formal closure**; do not invent run IDs.

## Remaining work and honest limits

- Compare every public React route and OpenAPI contract (including errors/permission denials), not only routes exercised by smoke tests.
- Map precise H4 tests for lost ACK, oversell, purchase-vs-unpublish and restore semantics. Missing evidence stays open.
- Current restore check proves individual dump round trips and table counts, not row-by-row equivalence or functioning applications on the restored triad.
- Complete an isolated cutover/abort **dry-run** that refuses a naive Legacy switch after new confirmed tickets. See `docs/H5-CUTOVER-ABORT-ROLLBACK-RUNBOOK.md`.
- Record release SHAs, exact successful CI run IDs, backup hashes, remaining risks, team decisions and sign-off.
- Archiving OpenSpec after architecture acceptance and switching production traffic are **separate decisions**. Production user/order backfill and real payment processing remain outside H5 scope.

No deployment, live migration, destructive restore or production cutover is performed here.
