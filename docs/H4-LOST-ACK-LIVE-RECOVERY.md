# H4 — Lost HTTP acknowledgements after Ticketing commit

This UAT adds deterministic fault injection to the existing three-service **disposable** GitHub Actions stack. No changes to ordinary production Compose files, Legacy, React or persistent databases. All microservice commercial flags remain OFF by default.

## How the fault is injected

The separate container `h4-fault-proxy` sits between Events and Ticketing only in the opt-in `docker-compose.h4-fault.yml` overlay, layered onto `docker-compose.h4-live.yml` only for the H4 CI job. It forwards private `/api/v1/internal/sales/gates/` HTTP requests to the fixed Ticketing service on its internal Docker network, including the internal service credential. The proxy cannot choose or redirect to another upstream.

Only for the dedicated UAT request IDs `h4-lost-publish-ack` and `h4-lost-unpublish-ack`, and only on an upstream HTTP 200 for respectively `/commands` or `/close-without-sales`, the proxy **allows Ticketing to commit** and then returns an artificial HTTP 503 once. A subsequent request using the exact same request ID is passed through unchanged.

This simulates **an ambiguous/lost successful acknowledgement**, not a TCP socket disconnect or a process crash. The proxy remains alive. HTTP 503 is an unknown write outcome to Events; it must not be interpreted as a committed public success.

## Durable recovery acceptance

The added `h4_fault_recovery_smoke.py` runner validates via actual Identity/Events HTTP and independent Events/Ticketing PostgreSQL:

1. Organizer creates a draft and publishes using the marker; first Events HTTP response must be **503** even though Ticketing opened gate v1/revision 1.
2. Events metadata must already be `published`; the publication intent and stable `command_id` must be persisted.
3. Repeating the same HTTP request returns **200**; same command ID, same gate v1 (no double-open).
4. The organizer sends `unpublish` with the other marker; first Events HTTP response must be **503** even though Ticketing closed gate v2/revision 2. Events metadata must still say `published`, and the same durable close intent must remain prepared.
5. Retrying returns **200** and draft metadata; the close intent is completed with the same command ID and gate remains v2 (no double-close).

Existing real HTTP tests for confirmed orders, historical replay and eight concurrent purchase-versus-close races also continue to run through the proxy *without fault markers*. The proxy is started before Events in the CI stack and is destroyed together with the dedicated `h4-live-ci` project at job end.

## Limitations before cutover

- The UAT simulates a lost successful HTTP acknowledgement with 503; it does **not** yet prove recovery from an actual killed Events/Ticketing process, TCP disconnect, database crash or corrupted response.
- The use of `X-Request-ID` to trigger fault injection belongs **only to this disposable UAT proxy**. Normal production topology does not contain that proxy.
- Purchase payment settlement, rate-limits, deployment rollback, routing cutover and real-process restart tests remain necessary before enabling any commercial flags.

## Reconciliation note (2026-11-25)

Original PR #82 remains open/unmerged; this replacement applies its fault-injection scenario to current `main` with an **additional H4-only Compose overlay**. The H5 Gateway job uses only `docker-compose.h4-live.yml`, preserving its normal direct Events-to-Ticketing upstream. This change must pass H4, H5 and the full CI suite before it can count as merged evidence; no production cutover is authorized.
