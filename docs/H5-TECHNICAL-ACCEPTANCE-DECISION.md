# H5 — Technical acceptance decision record

**Status:** PROJECT OWNER ACCEPTED BOUNDED H5; TEAM TECHNICAL/QA SIGN-OFF PENDING. **Not an authorization to deploy.**  
**Date prepared:** 2026-11-25  
**OpenSpec:** `h5-gateway-stage-i-cutover`  
**Last security change verified:** PR [#105](https://github.com/CipollaLucas/ticketing-tp/pull/105), merged at `ff3c3a49fa01897a0921cbc4d1363698fa52712f`; [CI run 45660017482](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45660017482), all twelve jobs successful.

## Recommendation for academic-stage review

**Project-owner decision on 2026-11-25:** ACCEPT BOUNDED H5 as an isolated academic proof of concept, with the limitations recorded here. This is an explicit user instruction from the project owner in the ChatGPT project conversation; it does not attest to an independent technical or QA review, and it does not by itself archive OpenSpec.

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
| Full error/response schema parity and URL fuzzing | #100 verifies method/path; #105 checks selected 401/404/503, private routes, fake credential | **Defer** exhaustive contracts/security review beyond the bounded TP prototype; keep explicit limitation | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |
| Full cutover/backfill/rollback dry-run | #98 runbook; #99 pure decision guard and synthetic Legacy ledger only | **Defer** true traffic switch, real Legacy DB reconciliation and post-write rollback to distinct migration project; do **not** claim operational readiness | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |
| Restored cluster end-to-end correctness and row-level equality | #97 isolated pg_dump/pg_restore SHA/counts | **Defer** operational DR and stronger reconciliation beyond the bounded TP UAT | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |
| TCP disconnect and process crash at commit boundary | #103 returns 503 after commit via proxy, #96 app restart after completed operation | **Defer** additional fault injection; no claim that those failure modes were proven | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |
| Production rollout or live commerce | Explicitly outside H5 proposal, no real payment settlement | **Exclude** from academic-stage architecture acceptance; requires entirely separate authorization | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |

**No item above is auto-approved.** Reviewers may instead require more tests; if any deferred item is required by the assignment's acceptance criteria, do not close H5 until performed.

## Review checklist

- [ ] Check the last merged `main` commit and exact CI runs, including PR #105.
- [x] Project owner reviewed the proposed bounded acceptance and explicitly approved this scoped decision in conversation on 2026-11-25.
- [ ] Independent technical/QA reviewers confirm or reject the proposed dispositions in the table.
- [ ] Confirm assignment requirements (microservice independence, purchase concurrency, audit bitacora) are adequately demonstrated.
- [x] Project owner recorded explicit `ACCEPT BOUNDED H5` on 2026-11-25; independent reviewer decisions remain pending.
- [ ] Only following acceptance: decide whether and how to archive **this architecture change** in OpenSpec, preserving deferred items as follow-up work.
- [ ] Preserve **PRODUCTION CUTOVER = NO-GO** unless an independent, separately reviewed migration and rollout decision authorizes it.

## Formal decision (not filled)

| Role | Name | Date | Decision |
| --- | --- | --- | --- |
| Technical reviewer | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING | PENDING | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |
| Test/QA reviewer | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING | PENDING | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |
| Project/team owner | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING | PENDING | OWNER ACCEPTED DEFERRAL; TEAM REVIEW PENDING |

**Project-owner scoped architecture acceptance:** APPROVED 2026-11-25. Independent technical and QA sign-off: PENDING.  
**OpenSpec H5 archive:** PREPARE CANDIDATE ONLY; WAIT FOR INDEPENDENT REVIEW AND EXPLICIT ARCHIVE DECISION.  
**Production migration/cutover:** NO-GO.

## Notes on academic delivery

This record lets the team present H5 as a successfully demonstrated architecture while remaining precise about what was **not** proven. It neither installs a runtime rollout switch nor archives OpenSpec. A green CI workflow is necessary evidence, but it does not supply missing reviewer decisions.

## Recorded approval provenance and boundaries (2026-11-25)

The project owner explicitly responded **“SI apruebo.”** to the question: “¿Aprobamos el cierre técnico de H5 con ese alcance y esas limitaciones, para preparar su archivo en OpenSpec?” This authorizes recording **owner acceptance of the bounded academic prototype and preparation of an archive candidate**, not claiming QA or second-reviewer signatures. Deferred requirements remain documented in the scope-disposition table. The user did not authorize real payment handling, Legacy cutover, data migration, or a production restore.

GitHub confirms PR #106 merged at `e837f5d74ab2c3af36a5fe74bd7ead1891905252`; its PR-head workflow [45661156433](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45661156433) completed with `success`. The exact archive commit and independent review approvals remain to be recorded at the time of archival.
