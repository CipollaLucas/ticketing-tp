# H3 Events — Stage I draft edit parity (#66)

**Existing Legacy capability:** `PATCH /api/v1/events/{event_id}` in `backend/app/events.py`. The new endpoint is owned by Events, uses Events DB and a hexagonal edit use case with a SQLAlchemy locked write port. It remains under `PROTECTED_DRAFTS_ENABLED=false` by default.

## Acceptance contract
- Valid owner (or administrator) can patch a nonempty subset of `name, description, venue, start_at, end_at` for an upcoming draft. Unknown fields and null values rejected with 422. Names and venue trim whitespace.
- Missing/invalid Bearer 401; customer 403; another owner 403; unknown event 404; published event 409.
- Invalid date, invalid status injection, malformed text or empty patch 422, no persistent mutation. `created_at` preserved, `updated_at` refreshed.
- Identity introspection fails closed, and repository uses row locking `SELECT FOR UPDATE`. No cross-database joins or SQL permissions.
- Full 10-field Stage I response shape. Tests against isolated Events database; no Legacy mutation or React rerouting.

## Explicit limitations
The Identity principal is verified before the Events row is locked. Cross-service revocation and metadata changes cannot be made atomic without coordination; the next publication/gate protocol needs a separate race test. This PR **does not publish events**, does not change gates or inventory, and does not enable sales.

CI and UAT: `ruff check .`, `mypy events_service`, `python -m pytest tests -v`, and CI PostgreSQL. Local PostgreSQL-specific tests can remain skipped until disposable DB is available. **No automatic merge.**
