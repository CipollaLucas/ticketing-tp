# H5 — Safe-abort decision rehearsal (synthetic Legacy, real disposable H5 sale)

This change adds a **fail-closed decision model**, *not* a production cutover mechanism, DNS switch, reconciliation engine or Legacy backfill.

## What the CI demonstrates

After H5's existing three-role HTTP and Chromium acceptance, app-restart recovery and three PostgreSQL archive restores:

1. A pure test verifies that a pre-write abort can be classified safe, but that an unrecorded new ticket prevents returning to Legacy.
2. The H5 customer authenticates again through disposable Gateway. The test verifies the event created by the original H5 smoke is still published and the original confirmed ticket belongs to the authenticated buyer.
3. A separate **synthetic in-memory Legacy ledger** has no knowledge of this newly confirmed ticket. Both active-write and frozen-write abort decisions are refused.
4. A hypothetical matching synthetic Legacy ledger is still marked `RECONCILIATION_REVIEW_REQUIRED`, never an automatic green light.
5. The script prints only pass/fail lines and no bearer, password or customer identifiers.

No service is reconfigured, no new Legacy container is launched and no original data is mutated. The runner must be exactly `h5-gateway-ci` with `H5_DISPOSABLE_ABORT_UAT=yes`.

## What this does NOT prove

- No real migration/backfill, write-freeze, data copy or DNS/NGINX rollback takes place.
- The synthetic ledger is not a real restored or migrated Legacy PostgreSQL database.
- No production-cutover RPO/RTO, post-write reconciliation approval, distributed freeze or irreversible payment transaction is tested.
- The current architectural H5 task for **a full disposable cutover/abort simulation** stays open until a truly isolated fixture with a separate Legacy DB and a controlled traffic-switch/write gate exists.

## Required evidence for final H5 acceptance

Attach exact successful CI run URLs for this test, previously merged UAT/recovery/restore tests, and explicit human review. A safe production traffic switch must be separately authorized and must not be inferred from this simulation or an OpenSpec archive.
