# H3 execution tasks

- [x] Reconcile the current implementation against H1-H5 and identify Events as next extraction boundary.
- [x] Define Events ownership, port boundaries, conservative state transition and opt-in rollout.
- [ ] Implement the standalone Events service skeleton with independent `events_db`, Alembic migration and healthcheck.
- [ ] Extract pure event domain and application use cases from Legacy while retaining public DTO/validation semantics.
- [ ] Add persistence repository, identity port and HTTP adapters with strict import boundaries.
- [ ] Implement internal/public preview API behind opt-in routing, without enabling state-changing cutover.
- [ ] Test independent PostgreSQL migration, negative roles, Identity outage, locks and publication failure behavior.
- [ ] Add isolated Docker Compose overlay and CI job for Events (build, ruff/mypy/tests/migrations/healthcheck).
- [ ] Run Legacy regression + React smoke without switching API; capture evidence.
- [ ] Prepare data migration and gateway integration dependencies for H4/H5; no active DB changes.
- [ ] Merge only after review/CI and archive only after H3 acceptance.
