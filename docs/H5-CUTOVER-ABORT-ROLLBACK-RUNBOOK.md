# H5 — Cutover, abort and rollback runbook (candidate; NO production authorization)

The independent H5 Gateway, Identity, Events and Ticketing environment is a disposable preview. No production traffic switch, live backfill or payments are authorized by this document.

## Required preflight and approvals

- Name incident commander, application owner, database owner and QA approver. Record exact release SHA, CI run IDs, environment, time window, RPO/RTO, backup hashes and an explicit separate GO/NO-GO decision.
- Freeze or coordinate existing writes. Inventory public routes, owner service and HTTP authorization; confirm no Legacy fallback or exposed internal endpoints.
- Verify each service migration in its own PostgreSQL database, service credentials, health, bounded HTTP timeouts and request-ID latency/audit logs.
- Compare Legacy and target identity/role mappings, event lifecycle, zones/seats, confirmed orders and tickets with read-only reports; reject missing, duplicate and mismatched records.
- Capture and verify three independent recoverable backups. Existing isolated `pg_restore` table-count checks do not establish row-level parity or an application run using restored DBs.
- Re-run concurrency, idempotency, publish-vs-zone, auth-denial, restart, restore, real Chromium and three-role HTTP UAT, documenting version and CI evidence. Treat omitted/unknown cases as blockers.

## Data migration and cutover constraints

Production backfill of users, sessions, orders, tickets and events is **out of scope** for the current H5 implementation. Design a separate, approved procedure with deterministic ID mappings, source fingerprints, replay-safe checkpoints, reconciliation reports, session policy and a verified single-writer/write-freeze mechanism.

Until such a plan is accepted, NO production traffic switch is permitted. A disposable dry-run must prove reconciliation and safe abort; this has **not** been demonstrated yet.

## Future rollout procedure — only after separate authorization

1. Freeze writes or activate a proven single-writer protocol; take consistent source snapshots.
2. Reconcile counts, IDs, authorizations, sold-ticket ownership and stock invariants. Stop on discrepancies.
3. Start approved independent services and Gateway with commercial flags **off**, then validate health, logs, protected routes and shared request IDs.
4. With authorization, switch a bounded fraction of traffic while preserving single-writer semantics. Never silently dual-write or fall back to Legacy.
5. Monitor latency, errors, failed Identity/Events dependencies, oversell, replay conflicts, confirmed orders and ticket visibility. Record explicit promotion/abort gates.

## Rollback decision matrix

| Condition | Before any new-system write | After new-system writes |
| --- | --- | --- |
| Gateway, DNS or app fails | Keep new flags off and retain verified Legacy entrypoint | Freeze new writes, keep all target records and reconcile before changing routes |
| Authentication/ownership mismatch | Block rollout and fix mapping | Freeze, preserve evidence, reconcile identities and ownership |
| Stock/order discrepancy | Abort without switching | Freeze, examine idempotency keys, versions and confirmed tickets; reconcile |
| Lost logging or backups | NO-GO | Stop expansion, preserve existing data/logs; incident commander decides next safe action |

**After the first new-system write, reverting DNS or NGINX to Legacy alone is unsafe.** Legacy may not contain those orders, and switching back can cause double sales. Never restore an older database snapshot over a database containing newer confirmed purchases. Define forward reconciliation/compensation with review, not automatic revert.

## Required disposable dry-run still open

Build a synthetic Legacy fixture and three fresh independent target DBs. Exercise pre-write abort; then a confirmed-ticket write followed by an abort. Verify writes halt and unsafe Legacy reversion is rejected. Reconcile all IDs, counts and tickets, validate repeat-key replay and publish the discrepancy report. No production data or credentials.

## Completion decision

Record per-service/gateway SHA, exact CI run links, backups/checksums, reconciliation results, residual risks, approved scope and signatories. Missing approval means NO-GO. Even if the H5 architecture change is archived after review, production migration and payment/cutover remain separately gated.
