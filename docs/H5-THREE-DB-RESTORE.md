# H5 — Three-database isolated restore verification

Part of OpenSpec change `h5-gateway-stage-i-cutover`; implementation evidence, **not** authorization to cut over production.

## Scope

After the existing successful H5 HTTP, React/Chromium and restart tests, CI:
1. Confirms Docker Compose project is exactly `h5-gateway-ci`, opt-in is explicitly enabled, and Docker container project/service labels match the three expected PostgreSQL services.
2. Verifies the disposable HTTP smoke's event/order/ticket/zone UUIDs actually exist and link across Events and Ticketing.
3. Runs PostgreSQL 16 `pg_dump --format=custom` for Identity, Events and Ticketing independently, storing the archives only in a transient runner directory.
4. Checks SHA-256 and restores each archive using a fresh, network-isolated, port-free PostgreSQL container. Does **not** restore over any source database.
5. Compares counts across all owned tables in each source and restored database. The offline verifier removes its isolated containers and the temporary archive directory.

## Boundaries

- Three databases are maintained separately; there is no shared cross-service PostgreSQL transaction.
- This validates the ability to restore each archive and table-row counts, not equality of every individual field, cross-service constraints in the restored cluster, RPO/RTO, encrypted off-site backup retention, or application functionality when pointed to the restored databases.
- The source transaction references are checked before backups; a full application-level reconciliation after restoring all three databases remains for later acceptance.
- Source databases exist only as tmpfs in GitHub Actions. No production hostname, secret, disk or persistent volume is accessed.
- Production rollback, legacy backfill, lost-ACK fault injection and cutover approvals remain separate gates.

Do not archive the OpenSpec umbrella change merely because this CI job passes.
