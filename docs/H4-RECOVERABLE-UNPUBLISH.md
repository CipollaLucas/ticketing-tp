# H4 — Recoverable unpublish on Events (issue #66)

## Stage I parity

Adds opt-in `POST /api/v1/events/{event_id}/unpublish`, strict `{}` payload, 10-field Event response, authentication through Identity on each invocation. Returns 409 if Ticketing reports any confirmed order; Events metadata remains published in this case.

## Safe ordering

1. Authenticated user + Events row owner validation.
2. Query Ticketing gate state. Only confirmed `open` at the matching Events revision is eligible.
3. Under an Events row lock, store an immutable close intent with UUID `command_id`, `expected_gate_version`, and next metadata revision. New additive Events migration: `0006_unpublish_intents`.
4. Send to Ticketing's **conditional** endpoint `/close-without-sales`, not generic close. Ticketing uses the same PostgreSQL gate row lock as purchases, checks confirmed orders, and atomically closes if none exist.
5. Only on a matching durable Ticketing acknowledgement set Events `status=draft`, advance revision, mark command completed and remove the obsolete publication intent in one Events transaction.
6. If the HTTP close ACK is lost after Ticketing commit, Events remains `published` and the next request replays exactly the same command. Ticketing's command history returns the original outcome; Events can then safely finalize to draft.

A completed close request replays without sending more remote commands. Metadata still published while gate closed is safe (no new purchases). A stale gate CAS or existing sales never permits unpublish.

## Safety

Feature gate `UNPUBLICATION_ENABLED=false`, independent of `PUBLICATION_ENABLED=false`. Existing `PROTECTED_DRAFTS_ENABLED=false` also required. Ticketing still requires `SALE_COMMANDS_ENABLED=false` unless explicitly activated in an isolated environment.

No automatic rollout, no activation for production or React, no Legacy changes, no data/volume deletion. Existing microservice publication is still under experimental flags. Further UAT needed with independent PostgreSQL services, concurrent purchase and closure across processes, backup-restore, timeout/restart, and gateway cutover before commercial activation.

## Tests
- Events application and HTTP tests: normal close, remote ACK loss, retry, confirmed-sales conflict, cross-owner/customer, Identity down/revoked, strict body, disabled flag.
- Ticketing PostgreSQL concurrency and no-sales invariants from PR #75.
- Events Alembic head 0006, Ruff, mypy and complete CI.
