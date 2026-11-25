# H3/H4 — Durable publish preparation, not sale activation

Issue #66, Stage I Legacy `POST /api/v1/events/{id}/publish` migration.

## Why this is needed

Legacy atomically locks an event with inventory and purchases in one PostgreSQL DB. In the new architecture Events and Ticketing have **separate** databases: a remote `open` may have committed even if Events loses the HTTP response. Generating another random command ID after the timeout is unsafe.

Ticketing already has an idempotent `GateCommand(command_id, event_id, expected_version, event_revision)` with a PostgreSQL gate lock shared by purchases and closes. Events previously had **no durable source for the command ID or metadata revision**.

## Implemented in this increment

- Events-only additive migration `0003_publication_intents` adds `events.revision` initialized to 0 without changing event status and an `event_publication_intents` table with one `prepared` command per event.
- Hexagonal `prepare_publication` verifies existence, owner/admin, draft, description and future dates, then persists a stable UUID command ID and next revision while **holding the Events row lock**.
- A retry after a successful DB commit retrieves the same command ID/revision from Events DB.
- While the intent is prepared, the pre-existing draft edit use case now refuses metadata changes (409), preventing stale content from being published later.
- No public route, no state change to `published`, no HTTP calls to Ticketing and **no sales opened**. Runtime commercial flags unchanged. No Legacy, React or Gateway modifications.

This is a **preparation stage** rather than a completed publish operation. Intent storage is durable, but Events has not yet implemented the revisioned metadata commit and remote command reconciliation.

## Remaining required behavior — DO NOT skip

1. Persist a complete command envelope including the expected Ticketing gate version; prepare must coordinate with a confirmed closed, provisioned gate, *without* creating a race while storing it. Reconcile stale/duplicate commands on retry.
2. Atomically mark metadata `published` and advance Events revision, then request Ticketing `open` with the persisted command ID. A failure after metadata commit must leave the gate closed until safely retried.
3. Closing sales: Ticketing must share the purchase gate lock, ensure **no confirmed orders** for Stage I `unpublish` (Legacy 409 if any), and persist the close command before returning. A separate GET count before close is **not sufficient** against races.
4. Only after durable close confirmation set Events back to draft. A timeout must not allow implicit re-opening.
5. Test replay after remote commit/HTTP timeout, crashes between each step, stale versions, concurrent purchase/close, role revocation, and database restore. Connect authenticated HTTP routes only with opt-in flags after tests.

## Safety

No database reset or destructive migration. This table is owned by Events and has only an Events-local foreign key. Existing event rows remain in their original status. Do not apply non-disposable migrations without backup/restore. This PR is not a cutover or permission to merge any commercial gate toggles.
