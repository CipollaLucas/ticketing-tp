# H3 draft use case — protected write boundary (increment 2)

This increment adds a **real write use case with a transactional Events-only persistence adapter**. It does not expose a new HTTP write route because the Events service does not yet have a verified Identity authorization adapter and race-control contract. A public endpoint accepting an arbitrary owner UUID would allow account impersonation.

## Implemented
- Immutable `DraftInput` and pure `create_draft` application case.
- Domain validation for future aware timestamps, name/venue/description and event status.
- DraftWriter port and SQLAlchemy adapter owning the local Events commit/rollback.
- Tests with fake port and Events-owned SQLite table, including rollback and invalid request protection.
- Architecture import-boundary test also covers `drafts.py`.

## Next separate slice under the same OpenSpec change
- Build an outbound Identity HTTP port/adapter with bounded timeout and fail-closed validation.
- Add an inbound protected Events draft endpoint that derives owner UUID **only from verified Identity principal**, never from request payload.
- Verify revoked sessions, role changes and outage cases; distinguish HTTP 401/403/503.
- Preserve public read-only catalog and existing Legacy/React behavior; do not enable publish/unpublish or migrate Legacy records before sale-state coordination.

This change requires no schema migration beyond Events 0001 and does not touch any existing Identity/Legacy database.
