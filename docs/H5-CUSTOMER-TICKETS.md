# H5 — Customer ticket listing in independent Ticketing

Part of OpenSpec change `h5-gateway-stage-i-cutover`. Implements read-only parity for React `GET /api/v1/me/tickets`. Only the authenticated customer may access their tickets; the customer ID comes solely from Identity internal introspection, not from path/query/body.

## Behavior

- Ticketing queries its own `orders → order_items → tickets` chain, filtered by `OrderRow.customer_id`, with stable ordering and pagination (limit 1..100, offset >=0).
- Returns `{items, total, limit, offset}` including ticket id, order_item_id, zone_id, seat_id and status.
- Historical allocations remain readable after Events is unpublished or sale gate is closed, and even with `PURCHASES_ENABLED=false`. No Events lookup or payment assertion.
- Missing bearer: 401; revoked/non-customer Identity: 403; Identity unavailable: 503; invalid pagination: 422.
- Gateway routes only exact `/api/v1/me/tickets` to Ticketing, leaving other unknown routes fail-closed. No Legacy fallback, no production cutover.
- Access to this read endpoint depends on a configured internal Identity secret; a missing/invalid configuration returns 503.

## Validation requirements

CI: Ruff, mypy, all Ticketing tests including `test_customer_tickets_http.py`, OpenSpec checks and routing assertion. Isolated multi-service HTTP UAT plus PostgreSQL with two customers still required before final H5 signoff. Full React parity remains incomplete due to pending zone creation and legacy POST /orders contract.

This PR only implements the read-only query. Do not archive the umbrella H5 change or activate production cutover.
