# H3/H4 sale-state coordination plan

- [x] Compare Legacy publication and purchasing data ownership against ADR-0005 and the migration roadmap.
- [x] Specify gate authority, closed-by-default behavior, local purchase lock, remote command/version/idempotency contract and failure cases.
- [ ] Review and accept sale-state coordination ADR with the team; do not assign reviewers automatically.
- [ ] Implement Ticketing-owned gate row, schema migration, command deduplication and version checking on an isolated H4 database.
- [ ] Move/port purchase transaction so inventory, idempotency, order persistence and sale-gate check use one PostgreSQL transaction and consistent lock ordering.
- [ ] Implement Ticketing internal authenticated open/close/query commands with timeout and command ID semantics.
- [ ] Implement Events application orchestration and outbound Ticketing HTTP adapter; **keep unpublish disabled** until concurrency tests are green.
- [ ] Prove real-PostgreSQL race tests for purchase-vs-close both orders and order replay after closing.
- [ ] Prove timeouts, interrupted responses, restarts, duplicated/reordered commands, Identity outage, and post-close metadata update failure.
- [ ] Validate data migration, rollback, Legacy regression, React smoke and Gateway readiness.
- [ ] Only enable remote publish/unpublish and H4 sales after CI/UAT review and explicit acceptance.
