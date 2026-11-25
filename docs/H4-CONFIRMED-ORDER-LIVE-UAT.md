# H4 — Confirmed sale blocks live HTTP unpublish

Extends the existing disposable three-service CI job `h4-three-service-live` from PR #77. The original draft/publish/unpublish/republish flow continues unchanged and remains an enforced check.

A new smoke runner, `services/ticketing/h4_confirmed_order_smoke.py`, executes under a **Ticketing-owned disposable PostgreSQL** container:

1. Obtain organizer and customer tokens from the independent Identity service over HTTP.
2. Create and publish a new event via Events HTTP.
3. Add a disposable general-admission zone in Ticketing's own database.
4. Purchase two tickets for the authenticated customer by running the **real** `purchase_tickets` use case with `SqlAlchemyPurchaseUnitOfWork`. This is a committed confirmed order, not a mock or manually inserted fake order.
5. Call Events `POST /api/v1/events/{id}/unpublish` over actual HTTP twice. Both must return **409**, because Ticketing's atomic `close-without-sales` checks confirmed orders while holding the purchase gate lock.
6. Verify gate is still `open v1/rev1`, the event remains publicly `published`, the confirmed order survives, two tickets remain valid, available capacity is exactly one, and historical purchase replay does not allocate new tickets.

**Scope:** this is a real purchase *application and SQL transaction* test; the Ticketing purchase HTTP adapter does not exist yet. Do not describe it as a browser purchase or completed purchase HTTP cutover. It does not verify actual payment processing.

**Isolation:** docker-compose.h3-contract.yml + docker-compose.h4-live.yml use three `tmpfs` PostgreSQL databases and a dedicated Compose project name, with no persistent volumes and no host-mapped ports. A defensive check refuses to execute the purchase smoke unless the DB name is `h4_ticketing_test` and `H4_DISPOSABLE_UAT=yes`. No regular developer database, Legacy records, or application Docker volume is modified.

Still required: purchase HTTP contract and role checking on its inbound adapter, live HTTP race between a simultaneous purchase and close, network timeout after committed close/open, process restart recovery, and full cutover procedures. All normal commercial flags remain default-off outside this disposable UAT.
