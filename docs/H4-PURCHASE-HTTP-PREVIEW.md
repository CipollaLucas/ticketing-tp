# H4 — Protected Ticketing purchase HTTP (opt-in)

Adds `POST /api/v1/events/{event_id}/orders` to independent Ticketing, with JSON `{"items":[{"zone_id":"UUID","quantity":2,"seat_ids":[]}]}`, required `Authorization: Bearer` and `Idempotency-Key` headers.

**Default-off:** `PURCHASES_ENABLED=false`. The public route returns 404 unless explicitly enabled. It does not change Legacy, React or normal Compose flags.

## Admission and ownership

1. Ticketing validates the shape and idempotency key without writing.
2. Ticketing calls **Identity's protected introspection** using a private 32+ character `IDENTITY_INTERNAL_TOKEN` and the user's bearer token. The customer's UUID comes only from Identity; a supplied `customer_id` field is forbidden. Customer role is required.
3. Ticketing reads Events' **public event detail** with strict UUID, `published`, future start and valid end checks. Missing, past, draft, malformed or unavailable events are rejected.
4. Only then is `purchase_tickets` invoked with Ticketing's owned `SqlAlchemyPurchaseUnitOfWork`. Within one PostgreSQL transaction it locks customer idempotency and the same sale gate row used by unpublish, allocates inventory, commits confirmed order and ticket rows.
5. First purchase returns 201; idempotent retry of same request returns 200 with `replayed=true`. Retries may not change order/ticket IDs. Conflicts return 409.

**Fail closed:** revoked Identity or unknown role, remote timeouts/errors, missing token, blocked metadata, closed sale gate, insufficient inventory, and idempotency collisions cannot authorize a new purchase. The admission lookup is never a substitute for Ticketing's gate lock: a concurrent close is handled by its own database transaction.

## Limits

- No payment provider yet; `confirmed` is the current domain's allocation/issuance state, not evidence of settled payment.
- Current HTTP admission requires the event still be publicly published even for historical key replay. The lower-level Ticketing UoW can replay after closure, but a distinct authenticated historical read/replay endpoint is required before general commercial cutover.
- Cross-service HTTP admission is a pre-check; the PostgreSQL gate remains the final concurrency authority.
- Additional traffic/abuse limits, request tracing, remote outage/restart recovery, gateway route cutover, and payment policy require separate work.

## Disposable UAT

`h4-three-service-live` uses the existing three `tmpfs` PostgreSQL databases. This PR changes its confirmed-sale smoke to purchase **through Ticketing HTTP** with Identity customer bearer and `Idempotency-Key`, verifies organizer cannot buy, then verifies two HTTP unpublish attempts return 409 while order, tickets, inventory and gate remain untouched. It also exercises same-key HTTP replay.

Do not enable `PURCHASES_ENABLED` outside this disposable environment. CI and the normal default flag remain conservative.
