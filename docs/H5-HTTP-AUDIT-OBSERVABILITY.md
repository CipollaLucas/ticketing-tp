# H5 — HTTP request audit and latency instrumentation

OpenSpec: `h5-gateway-stage-i-cutover` implementation increment.

## Responsibilities

- All three FastAPI entrypoints (Identity, Events and Ticketing) record one completion audit line per handled HTTP request: `request_id`, method, path without query parameters, outcome status, and monotonic `duration_ms`.
- A valid existing `X-Request-ID` is preserved and echoed; missing, malformed or oversized identifiers are replaced with generated UUID hex to avoid log injection.
- Audit timing starts before authentication, route validation and endpoint processing. Rejected requests (401/403/404/422) and exceptions (500) are measured. Exceptions are re-raised to preserve framework behavior.
- Logs intentionally omit credentials, Authorization, cookies, request/response bodies and query strings. This is a minimum-viable line log, not an immutable database audit trail.
- NGINX already records request identifier, HTTP status, request time and upstream time. The Gateway forwards its generated `X-Request-ID` into each upstream. A call between services must explicitly propagate it where applicable.

## Verification in this PR

Automated per-service middleware tests assert correlation round-trip, 404 status, duration, and that query/token secrets are not written to logs. Unit tests are not a substitute for full real-HTTP UAT: follow-up must verify cross-hop correlation, auth rejection and 500 behavior in CI on disposable services.

## Remaining closure gates

- Confirm both Gateway and backend container logs are actually collected and retained per local operational policy, including severity and rotation.
- Confirm identity-to-events-to-ticketing cross-hop request correlation with real HTTP.
- Demonstrate concurrent publication-versus-zone-creation invariants.
- Exercise restore/restart/rollback, browser-driven React and administrator journeys.
- Preserve cutover OFF by default. No production or payment activation is included in this PR.

Do not archive the umbrella H5 OpenSpec change based only on this increment.


## Cross-service evidence increment (proposed)

A real H5 Gateway smoke now captures the X-Request-ID of a successful event publication. That same publication calls Identity authorization and Ticketing sale-gate commands via Events. The CI verifier reads the **running disposable containers' logs**, and requires the exact publication ID plus an elapsed-time field in all four processes: NGINX Gateway, Identity, Events and Ticketing.

Per-service HTTP audit loggers have explicit INFO levels and a stream handler so audit messages are emitted in Docker stdout/stderr even when Python root logging remains at WARNING. Handler propagation remains enabled for existing unit tests.

This verifies one fully correlated published-event journey, not all possible internal RPCs, browser UI, or durable centralized audit storage. In particular, Ticketing public-event lookups from purchase admission do not yet forward the original request ID and are **not** covered by this publish-only proof. Do not claim universal trace propagation until those paths are tested.

The new CI check uses only the H5 disposable Docker project, never a production log or database. Test output prints the correlation ID, not authentication secrets.
