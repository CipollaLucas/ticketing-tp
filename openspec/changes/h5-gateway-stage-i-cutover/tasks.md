# H5 Gateway and architecture completion checklist

## Design and contracts

- [x] Identify Identity-only gateway limitations in main and document precise closure scope.
- [x] Record safety boundaries: Legacy remains untouched; separate opt-in preview; no payment/production cutover.
- [x] Inventory current public endpoints and compare service OpenAPI contracts with frontend calls (PR #100: twelve React methods/routes, not complete schema/error parity).
- [x] Agree route ownership and collision handling for /events and /events/{id}/orders (PRs #84, #89, #100; NGINX route precedence validated in isolated H5).

## Implementation (subsequent PRs under this change)

- [x] Implement full opt-in Gateway config with no Legacy fallback and no internal API exposure (isolated PR #84).
- [x] Add isolated Compose with Gateway + Identity + Events + Ticketing + independent DBs (PRs #84, #90).
- [ ] Add route/security tests: correct upstream, auth forwarding, fail-closed, 404/503, no secrets.
- [x] Add HTTP bitacora/timing validation across gateway/services (PRs #91, #93; publication trace, not all RPCs).
- [x] Execute three-role Stage I end-to-end API and React journeys while Legacy is stopped (PRs #90, #94, #95).
- [ ] Verify oversell/idempotency, purchase-vs-unpublish races, lost ACK/retries, restart recovery and DB restore as separate evidence lines.
- [ ] Produce operational rollback/backfill checklist; validate dry-run on disposable data.
- [x] Reconcile umbrella migration OpenSpec tasks with actual PR/test evidence (verified CI run register in docs/H5-FINAL-ACCEPTANCE-EVIDENCE.md; remaining work stays open).

## Completion

- [x] Record exact CI run IDs, tests, limitations and required team decisions (docs/H5-FINAL-ACCEPTANCE-EVIDENCE.md; explicit team acceptance still pending).
- [ ] Obtain PR approval, green checks and merge before marking tasks complete.
- [ ] Archive this change after acceptance, not during planning.
- [ ] Obtain explicit separate approval to activate any production cutover.

## Evidence note (reconciled 2026-11-25)

See `docs/H5-FINAL-ACCEPTANCE-EVIDENCE.md` for real successful GitHub Actions run IDs, commit SHAs and limitations. PR #92 was not merged; PR #101 replaced and resolved its concurrency fix in current `main`. Completed items above denote only implementation verified in disposable H5 CI, not a production cutover.

**Still unchecked:** exhaustive route/error behavior, the full H4 failure matrix with exact scenario mapping, a realistic separate Legacy cutover/backfill/rollback dry-run, formal QA/technical sign-off, and archive decision. These must be satisfied or explicitly dispositioned in an acceptance review. Real production cutover remains a distinct NO-GO requiring separate approval.
