# Coordinated sale-state design (H3/H4)

## Owners of truth

Events is authoritative only for metadata: `event_id`, `owner_id`, `start_at`, `end_at`, `draft/published`, and metadata revision. Ticketing is authoritative only for inventory, orders, tickets and a per-event `sale_state` = `closed|open` with monotonically increasing `sale_version`. Ticketing's gate row must be created through an idempotent integration action after the corresponding Events UUID is verified; there is **no cross-service foreign key**. `closed` is the default, including unknown events.

Do not infer authorization from an arbitrary UUID or public HTTP header. Internal communication must use service credentials, bounded timeouts, request IDs and a narrowly-scoped command identity. Events authenticates and authorizes the actor with Identity; Ticketing verifies that the caller is Events (not an end-user-supplied service credential).

## Local atomicity

Ticketing's order use case obtains the per-event sale gate lock **inside the same PostgreSQL transaction** as checking inventory, idempotency and persisting order/tickets. The lock must be held through commit. It rejects closed/unknown gates with no stock/order mutation. Close sales takes the **same gate lock**, serializing with all in-flight purchases. Lock ordering must be documented and consistent with inventory locks. A remote check of Events state, even with a version, is insufficient without this gate lock.

Any idempotent replay of a previously committed order is read-only and must remain accessible after closing sales; new purchases are denied.

## Commands and ordering

- **Open sales:** authenticated Events actor commits `published` metadata first, then calls Ticketing `open` with event UUID, metadata revision, expected gate version and unique command ID. Ticketing verifies service caller, event suitability and current gate state under lock; only after successful response may Events claim sales are open. HTTP failure leaves Ticketing's current state authoritative; the Event may remain published but unsellable (safe). Retry/reconcile with same command ID.
- **Close sales before unpublish:** Events asks Ticketing to close with UUID, expected version and command ID. Ticketing acquires the gate lock and transitions to closed, committing after any in-flight purchase. Only a confirmed closed state permits Events to persist `draft`. If the Events metadata update fails, sales remain closed; recovery must not automatically reopen without revalidating current metadata/revision.
- **Timeout or uncertain response:** neither assume success nor reopen. A privileged status query can reconcile gate state/version by command ID. Keep closed on uncertainty that could compromise safety. No synchronous two-phase commit claimed.
- **Concurrent commands:** expected versions implement compare-and-swap. Same command ID and same payload replay the stored result; reuse with different payload conflicts. Older revisions cannot reopen the gate. Duplicate requests cannot increment sale_version twice.
- **Identity outage:** Events refuses actor-triggered transitions; Ticketing refuses untrusted service commands; neither infers authorization from the public catalog. Lock/gate still protects purchase independently of remote Identity availability.

## Failure and race matrix

| Case | Expected outcome |
| --- | --- |
| Purchase locks gate before close | Purchase commits or rolls back fully; close waits, then closes |
| Close locks gate before purchase | New purchase sees closed and commits no stock/order change |
| Ticketing unavailable on close | Events remains published; no remote unpublish |
| Close persisted, Events update failed | Ticketing remains closed; no auto-open |
| Events published, opening Ticketing failed | Public metadata may be published; sale_state remains closed/uncertain, no new sale assumed |
| Duplicate close/open command | Same result, no duplicate version advancement |
| Open and close with stale versions | Reject stale command, preserve newest gate state |
| Replay old confirmed purchase after close | Return same historical order, no new stock mutation |
| Identity unreachable during transition | Refuse transition; no implicit privilege |
| Ticketing restart between request and response | Recover persisted gate state using command ID/version |

## Non-goals

No broker/outbox yet, no payment integration, no stock splitting, no SQL cross-service, no immediate remote publication endpoints, no Legacy mutation. The protocol requires explicit implementation and PostgreSQL concurrency tests before H3/H4 acceptance.
