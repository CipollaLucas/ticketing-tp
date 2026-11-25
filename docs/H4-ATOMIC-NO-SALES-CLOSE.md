# H4 — Atomic no-sales close for Stage I unpublish (issue #66)

Legacy `POST /api/v1/events/{id}/unpublish` returns 409 when any confirmed order exists. A separate HTTP count then gate close is NOT equivalent: purchases can commit in the gap.

## Implemented in Ticketing

New private `POST /api/v1/internal/sales/gates/{event_id}/close-without-sales`, protected by existing `SALE_COMMANDS_ENABLED=false` feature flag and authenticated internal service credential.

The use case `close_gate_without_sales`:
1. Checks prior command ID for idempotent replay.
2. Locks the **same** `sale_gates` row with `SELECT FOR UPDATE` used by `SqlAlchemyPurchaseUnitOfWork.allocate`.
3. Rechecks command replay after the lock.
4. Reads existence of confirmed orders for the event in the **same Ticketing transaction** while holding that lock.
5. If orders exist, raises `ConfirmedSalesExist` (409) and rolls back without closing. Otherwise performs the versioned CAS close and commits command history and gate change atomically.

A previously confirmed purchase cannot be invalidated. A concurrent purchase which obtains the gate row first will commit its order before no-sales close checks; close then returns 409. If close wins, the next purchase sees the closed gate and fails. Only the generic close command remains allowed for other explicitly authorized internal use cases; Events unpublish MUST use **this conditional endpoint**, never generic close.

## Tests

- Private HTTP: no-sales close, idempotent replay, orders present, stale CAS, non-close action, missing auth/flag/unknown gate.
- PostgreSQL integration: close then purchase fails; purchase holds gate lock first, commits, and no-sales close detects its confirmed order and leaves gate open.
- Existing Ticketing, Events, Identity, Legacy, frontend, migrations and backup/restore CI.

## Deliberate next step

**No public Events unpublish endpoint yet.** Events still needs a durable close command intent, independent authorized orchestrator, retry/reconciliation after remote HTTP timeout, metadata transition `published -> draft` only after confirmed conditional close, and UAT over live separate services/databases. Existing sales/open flags stay OFF. No schema migration, React or Gateway changes.
