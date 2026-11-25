# H5 — Technical acceptance decision record

**Status:** PENDING TEAM SIGN-OFF. **Not an authorization to deploy.**  
**Date prepared:** 2026-11-25  
**OpenSpec:** `h5-gateway-stage-i-cutover`  
**Last security change verified:** PR [#105](https://github.com/CipollaLucas/ticketing-tp/pull/105), merged at `ff3c3a49fa01897a0921cbc4d1363698fa52712f`; [CI run 45660017482](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45660017482), all twelve jobs successful.

## Recommendation for academic-stage review

**Candidate decision:** accept the H5 isolated microservice architecture implementation as a **bounded proof of concept** for the practical assignment, with its explicitly enumerated limitations. This is **a proposal to the reviewers**, not an accepted or archived change.

### Verified architecture and behavior

- Three independently persisted services: Identity, Events, Ticketing. Distinct disposable PostgreSQL instances; independent schema migrations.
- Opt-in, fail-closed browser Gateway, no fallback to Legacy; internal endpoints inaccessible from the public test interface.
- 12 React public method/path contracts mapped to live microservice OpenAPI; actual owner, customer and administrator HTTP and Chromium journeys.
- Postgres purchase/idempotency and sale-gate concurrency, including the zone/publication race fix in merged PR #101.
- Real H4 purchase versus unpublish tests; committed lost publish/unpublish ACK simulated as one HTTP 503 and successfully replayed in PR #103.
- HTTP access logs and publication request-ID correlation across Gateway/Identity/Events/Ticketing.
- Process restarts, idempotent replay, independent dumps and offline table-count restores; synthetic abort guard with a real disposable ticket.

The exact PR/run ledger is in `docs/H5-FINAL-ACCEPTANCE-EVIDENCE.md`; do not cite old PR #82 or #92 as merged. Security expansion: merged PR #105, run 45660017482.

## Scope-disposition register — reviewer action required

| Pending criterion | Actual evidence | Proposed disposition | Reviewer decision |
| --- | --- | --- | --- |
| Full error/response schema parity and URL fuzzing | #100 verifies method/path; #105 checks selected 401/404/503, private routes, fake credential | **Defer** exhaustive contracts/security review beyond the bounded TP prototype; keep explicit limitation | PENDING |
| Full cutover/backfill/rollback dry-run | #98 runbook; #99 pure decision guard and synthetic Legacy ledger only | **Defer** true traffic switch, real Legacy DB reconciliation and post-write rollback to distinct migration project; do **not** claim operational readiness | PENDING |
| Restored cluster end-to-end correctness and row-level equality | #97 isolated pg_dump/pg_restore SHA/counts | **Defer** operational DR and stronger reconciliation beyond the bounded TP UAT | PENDING |
| TCP disconnect and process crash at commit boundary | #103 returns 503 after commit via proxy, #96 app restart after completed operation | **Defer** additional fault injection; no claim that those failure modes were proven | PENDING |
| Production rollout or live commerce | Explicitly outside H5 proposal, no real payment settlement | **Exclude** from academic-stage architecture acceptance; requires entirely separate authorization | PENDING |

**No item above is auto-approved.** Reviewers may instead require more tests; if any deferred item is required by the assignment's acceptance criteria, do not close H5 until performed.

## Review checklist

- [ ] Check the last merged `main` commit and exact CI runs, including PR #105.
- [ ] Review all three technical outcomes and limitations.
- [ ] Approve or reject each proposed disposition in the table.
- [ ] Confirm assignment requirements (microservice independence, purchase concurrency, audit bitacora) are adequately demonstrated.
- [ ] Record names/roles/date and explicit `ACCEPT BOUNDED H5` or `REJECT / MORE TESTS`.
- [ ] Only following acceptance: decide whether and how to archive **this architecture change** in OpenSpec, preserving deferred items as follow-up work.
- [ ] Preserve **PRODUCTION CUTOVER = NO-GO** unless an independent, separately reviewed migration and rollout decision authorizes it.

## Formal decision (not filled)

| Role | Name | Date | Decision |
| --- | --- | --- | --- |
| Technical reviewer | PENDING | PENDING | PENDING |
| Test/QA reviewer | PENDING | PENDING | PENDING |
| Project/team owner | PENDING | PENDING | PENDING |

**Final architecture acceptance:** PENDING.  
**OpenSpec H5 archive:** NOT YET AUTHORIZED.  
**Production migration/cutover:** NO-GO.

## Notes on academic delivery

This record lets the team present H5 as a successfully demonstrated architecture while remaining precise about what was **not** proven. It neither installs a runtime rollout switch nor archives OpenSpec. A green CI workflow is necessary evidence, but it does not supply missing reviewer decisions.
