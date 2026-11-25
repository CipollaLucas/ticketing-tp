# H4 — Authenticated historical purchase replay after gate closure

## Problem

PR #79 introduced protected purchase HTTP. It correctly requires a verified Identity customer and a currently published, future Events record for **new** orders. But applying Events admission to a previously committed idempotent replay means a buyer cannot recover their order after an event is hidden, ended or Events is temporarily unreachable.

## Resolution

The POST purchase HTTP route now checks for an **existing customer-scoped idempotency key in Ticketing PostgreSQL after verifying Identity**:

- The same stable request hash returns the same confirmed order and ticket UUIDs with 200 and `replayed=true`, **without requiring Events to be online or public**.
- A key with a different payload is 409, regardless of whether the gate is open.
- A missing key is not authorization: the request must still pass public/future Events admission, Ticketing's sale-gate lock, inventory checks and a single purchase transaction.
- The same PostgreSQL customer advisory transaction lock serializes the historical lookup against concurrent same-key purchase; it does not create orders or reserve stock. If missing, the lookup rolls back before contacting Events.
- Identity bearer token validation and role `customer` remain mandatory for **both new purchase and historical replay**. No unauthenticated order retrieval, no cross-customer access, no extra data-provisioning endpoint.
- The explicit `PURCHASES_ENABLED=false` default is unchanged.

## Validation

- HTTP tests: historical replay after Events outage, revoked Identity denied, no new purchase during Events failure.
- PostgreSQL tests: closed gate replay of same order/ticket IDs, unchanged stock, different customer has no matching record, mismatched payload returns 409.
- Three-service disposable UAT: real customer purchase HTTP, confirmed-sale rejection of Events unpublish, then **disposable administrative gate close** via existing Ticketing internal command (not an Events unpublish), followed by successful HTTP historical replay and 409 for a brand-new purchase. The sale remains attached to the published event as per the legacy rule; this administrative closure is solely to reproduce a closed gate for the recovery test.

## Boundaries before cutover

No payment confirmation is implemented; `confirmed` represents order and ticket allocation. Real cross-process purchase/close races, recovery after service restart and payment flow remain separate acceptance gates. Do not enable the commercial feature flags outside the isolated UAT.
