# H5 — Final architecture acceptance evidence register

**Status:** candidate for technical acceptance, NOT archived and NOT authorized for production cutover.  
**Recorded:** 2026-11-25 UTC.  
**Change:** `openspec/changes/h5-gateway-stage-i-cutover`.

## Reproducible merge and CI evidence

The PR head commits below are verified merged in GitHub, with the cited CI workflow run conclusion `success`. The run links are immutable identifiers for reviewer inspection; they are not invented or user-reported IDs.

| Capability | Merged PR | Head SHA | Successful workflow run |
| --- | --- | --- | --- |
| Independent H5 Gateway | [#84](https://github.com/CipollaLucas/ticketing-tp/pull/84) | `d89f58e51e65` | [45626149847](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45626149847) |
| React purchase alias and idempotency | [#89](https://github.com/CipollaLucas/ticketing-tp/pull/89) | `44033923446f` | [45633140719](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45633140719) |
| HTTP journey via Gateway | [#90](https://github.com/CipollaLucas/ticketing-tp/pull/90) | `38d0704128f4` | [45636780692](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45636780692) |
| HTTP audit logging | [#91](https://github.com/CipollaLucas/ticketing-tp/pull/91) | `50f1672dccf7` | [45638495479](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45638495479) |
| Publish trace shared by four processes | [#93](https://github.com/CipollaLucas/ticketing-tp/pull/93) | `2fdbbd896111` | [45643247635](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45643247635) |
| Three-role HTTP RBAC UAT | [#94](https://github.com/CipollaLucas/ticketing-tp/pull/94) | `2c07b2c183bd` | [45644037419](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45644037419) |
| Real React Chromium UAT | [#95](https://github.com/CipollaLucas/ticketing-tp/pull/95) | `598014d4edf2` | [45646713198](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45646713198) |
| Application restart and replay | [#96](https://github.com/CipollaLucas/ticketing-tp/pull/96) | `cfd06e729e69` | [45648822070](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45648822070) |
| Three independent offline DB restores | [#97](https://github.com/CipollaLucas/ticketing-tp/pull/97) | `c05e34d33a10` | [45651611862](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45651611862) |
| Operational rollback runbook | [#98](https://github.com/CipollaLucas/ticketing-tp/pull/98) | `a1272329b184` | [45653150201](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45653150201) |
| Synthetic post-write abort guard | [#99](https://github.com/CipollaLucas/ticketing-tp/pull/99) | `f9c531e9a491` | [45653893881](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45653893881) |
| React-to-OpenAPI method/route ownership | [#100](https://github.com/CipollaLucas/ticketing-tp/pull/100) | `46ead9499b22` | [45654732837](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45654732837) |
| Lost-ACK publish/unpublish recovery (replacement for unmerged #82) | [#103](https://github.com/CipollaLucas/ticketing-tp/pull/103) | `0299fc6de7ec` | [45658053960](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45658053960) |
| Zone/gate concurrent serialization (replacement) | [#101](https://github.com/CipollaLucas/ticketing-tp/pull/101) | `9ac655a98a95` | [45655559719](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45655559719) |

**Important correction:** Original [PR #82](https://github.com/CipollaLucas/ticketing-tp/pull/82) was never merged and was closed as superseded by #103. Original [PR #92](https://github.com/CipollaLucas/ticketing-tp/pull/92) was never merged. It was closed as superseded; #101 carries the current-main concurrency fix. Do not cite #92 as merged evidence.

For CI runs #97, #99, #100, #101 and #103 above, the GitHub Actions job inventory was verified: all 12 jobs had `success`, including `h5-gateway-stage-i`, `h4-three-service-live`, `ticketing`, `events`, `identity`, `frontend`, `backend`, `openspec`, `docker`, `db-backup-restore`, `identity-contract` and `h3-identity-events-contract`.

## Three technical challenges from the assignment

### Prevent duplicate ticket sales

The Ticketing purchase unit of work owns orders, tickets and available inventory in independent PostgreSQL. The Gateway smoke checks the same idempotency key returning a 200 replay with the identical order/ticket and no second stock decrement; concurrent gate/zone transition is tested by replacement #101. This is stronger than a mock-only test, but the H4 test suite now includes intentional lost ACK for publish/unpublish (#103) and a real-HTTP purchase-versus-unpublish race. These do not prove an actual TCP disconnect or process death during commit; additional fault scenarios remain outside the demonstrated scope.

### Independent microservice architecture

Identity, Events and Ticketing maintain distinct PostgreSQL databases. The H5 Gateway routes the public API with internal endpoints blocked and no Legacy fallback. Real HTTP, role-authorization and Chromium UI tests are run against three-service disposable Compose. Method/path ownership of the twelve React API functions is verified against live OpenAPI, but not full schema and error-contract parity. Rollout is separate.

### HTTP audit log and timings

Identity, Events and Ticketing audit request ID, method, route, result and elapsed time; the Gateway includes request and upstream duration. A real publication trace was verified in the four processes. This does not establish universal cross-hop trace propagation or a centralized durable security audit store.

## Proven boundaries and unresolved acceptance items

- **Independent DB backup/restore:** #97 demonstrates dump/checksum/restore and table counts using fresh, disconnected PostgreSQL. It does not prove row-by-row equality or that live applications function against the restored trio.
- **Restart:** #96 verifies continued ticket/order visibility and same-key replay after restarting application containers with DBs still running. No crash-during-commit fault injection is implied.
- **Abort:** #99 uses a real disposable Ticketing sale but only an **in-memory synthetic Legacy ledger** and a pure safe-abort decision function. It does not switch traffic, perform backfill, or prove a full post-write rollback.
- **Legacy migration:** copying production users, sessions, events, orders and tickets, reconciliation, payments, RPO/RTO and cutover permission remain outside this architectural implementation and require a separate approved change.
- **Unverified exact acceptance lines:** exhaustive route/error parity, unexercised failure modes (actual TCP disconnect, crash-during-commit) and exact per-scenario QA sign-off, full end-to-end restore-on-restored-cluster reconciliation and a realistic disposable traffic-switch rollback rehearsal still need evidence or explicit scope disposition.


## PR #103 lost-ACK reconciliation

PR #103 is merged (merge SHA `8e4963dfcadb56920d3c5c17ade29c4751f6192b`). Run [45658053960](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45658053960) is `success` with all twelve jobs successful, including `h4-three-service-live` and `h5-gateway-stage-i`. The dedicated H4-only fault overlay simulates a successful Ticketing gate write whose first acknowledgement is replaced with HTTP 503; the next publish/unpublish call must recover without incrementing gate versions or duplicating commands. The old PR #82 was explicitly closed unmerged after this replacement, and the H5 normal gateway remains isolated from the H4 proxy.

**Not proven:** actual socket termination, partial TCP frames, process crash mid-transaction or operational rollback against a migrated real Legacy database. These omissions must remain visible at acceptance.

## Technical decision (pending review)

Candidate decision: **H5 independent microservice architecture implemented and demonstrated in disposable CI**. This document does NOT itself attest that every H5 OpenSpec task is complete. A reviewer must explicitly disposition the remaining lines (test, defer to a separate change with rationale, or reject), accept bounded evidence, and record approval before archiving.

**Do not automatically archive H5 or enable production flags.** Production route switch remains **NO-GO** until separately approved, including a single-writer and post-write reconciliation plan.

## Sign-off record (to be completed by the team)

| Field | Status |
| --- | --- |
| Final release commit on `main` | To record on acceptance date |
| Technical reviewer / date | Pending |
| QA reviewer / date | Pending |
| Remaining acceptance gates disposition | Pending |
| H5 OpenSpec archive decision | Pending |
| Production cutover authorization | **NO-GO / outside this change** |
