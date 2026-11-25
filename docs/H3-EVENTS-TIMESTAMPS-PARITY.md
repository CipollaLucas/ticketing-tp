# H3 Events — Timestamp contract parity, Stage I

Source: `backend/app/models.py::Event`, `backend/app/events.py::EventResponse`, `docs/API-ETAPA-I.md`, issue #66.

This increment adds `created_at` and `updated_at` as owned, timezone-aware, non-null Events columns with additive Alembic revision `0002_event_timestamps` and returns both fields in:

- `GET /api/v1/events` (catalog)
- `GET /api/v1/events/{id}` (published detail)
- `GET /api/v1/owner/events` (protected owner list)
- `POST /api/v1/events` (protected draft creation)

New drafts receive equal timestamps at creation, persisted consistently. Reads return saved timestamps. The older Legacy contract includes exactly `id, owner_id, name, description, venue, start_at, end_at, status, created_at, updated_at`; HTTP tests assert this shape.

## Existing-data caveat
Events' original independent `0001_events` schema **did not record timestamps**. Revision `0002` initializes these columns for **existing H3 records at migration time**, not the historic creation or update time. Values for imported records must be supplied by a separate, reviewed data-import process if source records and timestamps are available. Do **not** claim synthetic migration timestamps are authentic historical metadata.

## Safety
- Additive schema; no Legacy schema, Gateway, React or commercial flags changed.
- No database reset, truncation, or rewrite of an existing business record.
- Before applying in any non-disposable deployment: backup and verify restore, then run `alembic upgrade head` using service-owned DB credentials. Local test environment may have no PostgreSQL DB, with integration executed in CI.
- Domain/application stay independent of ORM/HTTP; timestamp values are carried through the existing ports.
- This closes the **timestamp response fields**, but not yet edit/publish/unpublish, data import or full end-to-end parity. No cutover approved.

## Acceptance
- [ ] Events Ruff, mypy, pytest including new contract test.
- [ ] Independent PostgreSQL Alembic up/down in CI; no foreign keys to other services.
- [ ] Legacy/React/Identity/Ticketing regression green.
- [ ] Review and manual squash merge only after evidence.
