# H3/H4 — Durable closed-gate CAS snapshot for publication

Issue #66: move the existing Stage I publish flow out of Legacy without opening sales during incomplete coordination.

PR #72 introduced a persisted `PublicationIntent` with command ID and Events metadata revision. This increment records the Ticketing **expected gate version** in that same intent (new additive Alembic revision `0004_publication_gate_snapshot`).

## Safe workflow (no public route yet)
1. An authorized organizer prepares the intent, atomically under the Events event-row lock (existing behavior).
2. The future coordinator uses an authenticated Ticketing port to obtain the **actual registered closed gate** state (provision before reading; Ticketing's unknown-event closed default is not proof of provisioning).
3. It calls pure `record_closed_gate_snapshot` with that state. Events locks its own event row, checks ownership, draft status, prepared intent, event revision and closed gate/version/revision, then persists `expected_gate_version` with a local transaction.
4. A replay preserves command ID, revision and expected version. If the gate's version changed, it fails 409 for reconciliation instead of silently rebinding. The eventual `open` must use Ticketing's CAS mechanism, which prevents a stale snapshot from opening a gate.

There is **no HTTP route for steps 1–4**, no metadata transition to `published`, no Ticketing open, and no commercial cutover. This commit adds a safe, durable precondition, not a completed publishing workflow. Token validation and read/provision orchestration must occur in the future HTTP coordinator with Identity verified on each request.

Existing rows' `expected_gate_version` is NULL until validated; revision 0004 does not infer stale gate versions or rewrite event status. All Legacy/React/Gateway behavior unchanged.

## Next acceptance boundary
- Verify actual provisioned gate (not synthesized unknown-closed), re-read authorization.
- Atomically commit Events metadata `published` and advance revision with saved command identity.
- Send Ticketing `open` using persisted command ID, expected gate version and metadata revision; reconcile timeout via idempotent command replay and reject stale versions.
- For unpublish, ensure no orders by taking the *same Ticketing gate lock* used by purchase in one local transaction, then close before changing Events metadata.
- Real PostgreSQL concurrency/failure-injection tests and multi-service UAT; flags off until proven.

## Validation
Events Ruff, mypy, pytest; CI PostgreSQL Alembic 0004; all other CI jobs. No destructive Docker commands or production data changes.
