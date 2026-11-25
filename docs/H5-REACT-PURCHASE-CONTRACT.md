# H5 — React Stage I purchase contract against independent Ticketing

OpenSpec: `h5-gateway-stage-i-cutover`. This increment restores the existing browser purchase request shape without introducing a second business transaction.

## Public routes

- Existing independent H4 endpoint: `POST /api/v1/events/{event_id}/orders` with `{items:[...]}`.
- React Stage I compatibility: `POST /api/v1/orders` with `{event_id, items:[...]}`.
- Both use the **same** Ticketing `create_order` handler and local PostgreSQL purchase unit of work. The browser cannot supply `customer_id`, sale-gate state, total or ticket status.
- `Idempotency-Key` remains required. New purchase returns 201 with `Idempotent-Replayed:false`; same-key matching replay returns 200 with `Idempotent-Replayed:true` and the same order ID. Key reuse with altered intent remains conflict.
- Identity verification is required even for replay. New purchases additionally verify Events and serialize sale-gate/stock/order/ticket mutations in Ticketing. No payment capture is implied.
- NGINX routes `/api/v1/orders` exactly to Ticketing; unknown routes still reject, no Legacy fallback.

## Acceptance

1. CI: OpenSpec, Ruff, mypy, Ticketing pytest and PostgreSQL concurrency/idempotency.
2. Test the browser alias and existing event-scoped endpoint for equivalent authorization, replay status and payload contracts.
3. Three-service disposable gateway UAT with React calling the alias and Legacy unavailable.
4. Preserve default-off purchase flags outside explicit disposable UAT.
5. Review race `publish vs zone creation` separately; this route does not solve that previously documented gap.
6. Continue full H5 audit, failure recovery, safe rollback and cutover before archiving the change.

No local Docker test, CI run or deployment was performed while preparing this PR. This is not a production cutover.
