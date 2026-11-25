# H4 — Cross-process HTTP purchase versus unpublish race UAT

The existing Ticketing PostgreSQL integration tests already prove both serialization orders under the same `sale_gates` row lock. This change adds the missing **inter-service** acceptance gate.

The CI job `h4-three-service-live` launches three independently running HTTP services (Identity, Events, Ticketing) and three independent disposable PostgreSQL databases stored in `tmpfs`. New runner `h4_concurrent_http_smoke.py` exercises **eight independent events**.

For each event:
1. Create and publish using real authenticated Events HTTP; seed a new general-admission zone only in the disposable Ticketing DB.
2. Launch a buyer and event owner concurrently from separate Python threads, each with an independent `httpx.Client`. A `threading.Barrier` synchronizes request launch but **does not force which PostgreSQL gate row lock wins**.
3. The buyer invokes the protected Ticketing `POST /api/v1/events/{id}/orders`; the owner invokes Events `POST /api/v1/events/{id}/unpublish`, which uses Ticketing's atomic `close-without-sales`.
4. The only acceptable outcomes:
   - **Buyer wins:** HTTP purchase 201, unpublish 409, sale gate remains open v1, one confirmed order and valid ticket, stock decremented once, Events publicly published.
   - **Closer wins:** unpublish 200, purchase 403 (Events hidden) or 409 (Ticketing gate closed), gate closed v2, no orders or tickets, stock unchanged, Events public detail 404.
5. Any state combining a confirmed sale with closed gate or hidden event fails CI. There are no arbitrary sleeps, no shared SQL transactions between services, no mock orders and no data mutations outside the disposable Compose project.

Existing H4 integration tests for historical replay, duplicate requests and sold-event 409 remain mandatory. No production flags are changed, no Legacy/React cutover, no payments, and no local persistent volume operations.

Limitations: a barrier only coordinates test-client request launch, not the actual database lock-acquisition order. Separate PostgreSQL tests already force each lock order. A future fault-injection increment must cover service restarts and ambiguous network timeouts.
