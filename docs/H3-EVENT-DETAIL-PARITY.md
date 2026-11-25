# Issue #66 — Stage I public event detail extraction

**Target:** `GET /api/v1/events/{event_id}` from the functional monolith (`backend/app/events.py:public_event`) into Events, using its existing `SqlAlchemyEventReader.by_id` and application-layer port.

## Verified behavioral contract

- Published event => HTTP 200, including when event start is already in the past.
- Draft or unknown event => indistinguishable HTTP 404 `{"detail":"Event not found"}`; no draft metadata leakage.
- Invalid UUID => FastAPI HTTP 422.
- Existing public catalog `GET /api/v1/events` remains future published only.
- Independent Events DB only, no Legacy/Identity SQL access.

## Known remaining **representation** gap — not full HTTP schema parity

Legacy `EventResponse` includes `created_at` and `updated_at` timestamps. Independent Events `EventRecord/EventResponse` and its current schema **do not yet include these fields**. This PR restores **route + access semantics only**, not byte-for-byte compatibility with the entire Legacy JSON schema. Full Stage I representation compatibility requires owned database migration for timestamps, record and HTTP response updates, followed by contract comparison for `GET /events`, `GET /events/{id}`, `POST /events` and `GET /owner/events`. Never declare cutover readiness until fixed.

## Acceptance

- CI `events`: Ruff, mypy, SQLite HTTP behavior tests, PostgreSQL integration/migration.
- Regression: remaining modules green.
- No Gateway routing changes, no React switching, no Legacy changes; user merges manually.
