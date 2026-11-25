# H5 Gateway and architecture completion checklist

## Design and contracts

- [x] Identify Identity-only gateway limitations in main and document precise closure scope.
- [x] Record safety boundaries: Legacy remains untouched; separate opt-in preview; no payment/production cutover.
- [ ] Inventory current public endpoints and compare service OpenAPI contracts with frontend calls.
- [ ] Agree route ownership and collision handling for /events and /events/{id}/orders.

## Implementation (subsequent PRs under this change)

- [ ] Implement full opt-in Gateway config with no Legacy fallback and no internal API exposure.
- [ ] Add isolated Compose with Gateway + Identity + Events + Ticketing + independent DBs.
- [ ] Add route/security tests: correct upstream, auth forwarding, fail-closed, 404/503, no secrets.
- [ ] Add HTTP bitacora/timing validation across gateway/services (all statuses, request ID).
- [ ] Execute three-role Stage I end-to-end API and React journeys while Legacy is stopped.
- [ ] Verify oversell/idempotency, purchase-vs-unpublish races, lost ACK/retries, restart recovery and DB restore as separate evidence lines.
- [ ] Produce operational rollback/backfill checklist; validate dry-run on disposable data.
- [ ] Reconcile umbrella migration OpenSpec tasks with actual PR/test evidence (no retrospective unverified checkmarks).

## Completion

- [ ] Record exact CI run IDs, tests, limitations and required team decisions.
- [ ] Obtain PR approval, green checks and merge before marking tasks complete.
- [ ] Archive this change after acceptance, not during planning.
- [ ] Obtain explicit separate approval to activate any production cutover.
