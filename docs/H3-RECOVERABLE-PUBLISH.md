# H3/H4 — Recoverable Stage I publish command (issue #66)

**This PR implements the publish route but keeps it OFF by default.** It preserves the original `POST /api/v1/events/{id}/publish` 10-field response shape and strict empty-object body, and uses the two independent DBs and hexagonal ports. React and Legacy are untouched.

## Commit order / recovery guarantee

1. Events introspects the organizer's Identity session on **each HTTP call** and validates event ownership, draft/future metadata, description.
2. Under an Events-local row lock, it prepares a stable `command_id` and `event_revision`. Replay uses the same intent.
3. It requests closed-only provision at Ticketing using a private service token. Unlike a status GET, provision confirms the gate exists and returns its durable state.
4. Events stores Ticketing's closed gate CAS `expected_gate_version` in its own intent, after a separate commit; no Events row lock is held during the remote HTTP call.
5. Events atomically updates `events.status=published`, advances `events.revision`, and changes the durable intent phase to `metadata_published`. A timeout/restart after this point leaves **metadata published but selling closed**, which is a deliberate conservative state.
6. Events sends Ticketing the persisted `GateCommand(command_id, event_id, action=open, expected_version, event_revision)`. Ticketing serializes with purchase/close using its gate row lock; stale versions/duplicate divergent commands are rejected. A lost HTTP ACK returns 503; reissuing the same publication replays the same command ID and expected version and can recover after a successful remote commit.

**Only a successful matching Ticketing acknowledgement returns HTTP 200.** Missing/invalid Identity fails 401/503, wrong ownership 403, conflict 409, remote uncertainty 503. A published event can remain visible while sales are not yet open; clients must never infer purchasability from Events metadata alone.

## Opt-in; do not activate commercially

New Events flag `PUBLICATION_ENABLED=false`; the existing `PROTECTED_DRAFTS_ENABLED=false` also remains required. Ticketing requires `GATE_PROVISIONING_ENABLED=false` and `SALE_COMMANDS_ENABLED=false` unless intentionally set in disposable UAT; all default to disabled. Service token must be 32+ characters, use internal network access only.

**No production activation yet.** Inventory and purchase HTTP cutover, authenticated purchase behavior, unpublish/no-sales atomics, and distributed crash+concurrency UAT are not complete. This PR is an isolated implement-and-test step, not a claim that the commercial system can switch over. Live React remains on Legacy.

## Migration

Events migration `0005_metadata_published_phase` expands the intent-phase constraint and does not alter existing rows by itself. The downgrade is only valid if no `metadata_published` records exist; do not downgrade active in-progress publication without recovery. Back up/verify restore before applying to non-disposable DB. No cross-context foreign keys.

## Acceptance matrix
- [ ] Ruff, mypy, all Events tests, 0005 Alembic, all GitHub CI jobs.
- [ ] HTTP tests: same ten fields, strict empty payload, unauthorized customer/other owner, disabled flag, Identity down, replay.
- [ ] Orchestrator tests: closed gate provisioning, published commit, remote ACK lost after open commit, one command ID, stale version rejection.
- [ ] Full multi-process isolated Ticketing+Events+Identity UAT, PostgreSQL concurrency, unpublish with sold orders and restore validation **before enabling flags**.

