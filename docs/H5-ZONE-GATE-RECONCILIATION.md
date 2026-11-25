# H5 — Restoring a missing concurrency change in main

During final OpenSpec evidence reconciliation, GitHub showed PR #92 (`fix/h5-zone-publication-race`) still **open, unmerged and conflicting**. The checked-out main branch therefore did not contain the proposed closed sale-gate insert and lock used to serialize zone changes against gate opening. Earlier acceptance notes describing #92 as merged were incorrect.

This replacement branch starts from **current main**, carries forward the narrow fix, and preserves all H5 HTTP/browser/restart/restore changes merged after #92 was proposed.

## Expected invariant

Ticketing must insert a uniquely keyed closed `sale_gates` row with `INSERT ... ON CONFLICT DO NOTHING`, then lock it with `SELECT ... FOR UPDATE` before writing new zones/seats. Existing gates cannot be silently reset. Sale-gate open CAS and zone mutation serialize on the **same PostgreSQL row**.

- If a zone transaction commits first, subsequent gate opening sees the committed inventory.
- If gate opening obtains the lock first, zone creation sees an open gate and rejects with HTTP 409 without writing inventory.
- Preflight owner/draft verification still happens in Events. There is no distributed lock on Events metadata, and this test does **not** prove global cross-database serializability.

## Acceptance

- Ruff and mypy for Ticketing
- Unit tests of first zone, already-open gate and versioned closed gate
- PostgreSQL race test
- H5 disposable Gateway UAT including a late-zone request after publication
- Whole H5 CI suite green
- Review the old PR #92 as superseded and close it **only after** replacement merges.

**No cutover, application rollout, Legacy migration, or OpenSpec archive is part of this change.**
