# H5 — OpenSpec archive readiness and deferred follow-up

**Owner decision:** ACCEPT BOUNDED H5 academic architecture, 2026-11-25.  
**Technical/QA independent sign-off:** pending.  
**Archival status:** candidate only; the change stays at `openspec/changes/h5-gateway-stage-i-cutover` until accepted by reviewers.  
**Production cutover:** NO-GO.

## Before archiving

1. Confirm `main` has merged PR #106 and the owner-acceptance record. Confirm the final PR CI.
2. Review `docs/H5-FINAL-ACCEPTANCE-EVIDENCE.md` and `docs/H5-TECHNICAL-ACCEPTANCE-DECISION.md`. Have technical and QA reviewers explicitly approve or reject each deferral; names and dates must be entered by those reviewers, not inferred from green CI.
3. Validate the `gateway-stage-i` OpenSpec delta and verify no requirement contradicts the deferred bounded prototype scope. Preserve the exact requirement and acceptance record.
4. Create an archive-only PR using the project's installed OpenSpec CLI: `npx --yes @fission-ai/openspec@2.1.1 archive h5-gateway-stage-i-cutover` (inspect `--help` and review the resulting diff before committing). If the CLI requires all tasks checked, **do not falsely mark unsupported tests as passed**; first document or adjust the change scope with reviewer approval. Confirm whether the archive operation updates central specs; do not force the operation to make an invalid spec pass.
5. Confirm only H5 OpenSpec files and intended canonical specs change. No changes to Legacy, Compose production, commercial flags, databases, migrations or payment APIs.
6. Run strict OpenSpec validation and normal PR CI, inspect file moves/spec delta and merge only after independent approval. Record archive commit and reviewers in the acceptance document.

## Deliberately deferred scope

| Separate follow-up | Why it is not part of bounded H5 acceptance |
| --- | --- |
| Real backfill, single-writer cutover and reverse reconciliation | #98 is a runbook; #99 simulates an abort guard with a synthetic Legacy ledger, not a working traffic switch |
| Production-grade disaster recovery | #97 checks independent PostgreSQL dump/restore/counts, not complete row parity or an app boot against the restored cluster |
| Exhaustive response contract and security assessment | #100 verifies twelve method/path contracts; #105 samples private path denial and HTTP 401/404/503 |
| Actual TCP severance/crash-at-commit fault injection | #103 injects a post-commit HTTP 503, not a killed process |
| Payment settlement and deployment approval | Never implemented or authorized in H5 |

**These are explicit exclusions from the proposed academic scope, not tests marked successful.** If faculty or team acceptance requires any item, return to implementation before archiving.

## Ownership and approval gate

The project owner's explicit “SI apruebo” is recorded as **academic technical scope acceptance**. It is not a signature by other team members. The archive is ready for reviewer action, **not performed** by this document.

## Evidence links

- [Final PR/run inventory](H5-FINAL-ACCEPTANCE-EVIDENCE.md)
- [Owner and independent review decision record](H5-TECHNICAL-ACCEPTANCE-DECISION.md)
- [Rollback safety runbook](H5-CUTOVER-ABORT-ROLLBACK-RUNBOOK.md)
- [Gateway route-security evidence](H5-GATEWAY-ROUTE-SECURITY-EVIDENCE.md)
