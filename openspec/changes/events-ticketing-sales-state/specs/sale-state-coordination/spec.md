# Sale-state coordination — requirements

## ADDED Requirements

### Requirement: Ticketing alone authorizes new sales

The system SHALL keep a durable per-event sale gate in Ticketing's database. An unknown event MUST be closed. A purchase MUST acquire the gate lock and check it within the same transaction that atomically modifies stock and records the order/tickets.

#### Scenario: close racing with purchase
- GIVEN a published event with sales open
- WHEN a purchase and a close command run concurrently
- THEN exactly one lock order determines the outcome
- AND an order either commits completely before close or is rejected without any stock/order mutation after close
- AND no order commits after the close transaction has committed.

#### Scenario: idempotent replay after close
- GIVEN a previously confirmed order and its idempotency key
- WHEN sales close and the exact purchase request is replayed
- THEN the previous order is returned with no new stock or order changes.

### Requirement: Safe Events transitions

The system SHALL prevent a remotely requested unpublish until a close of Ticketing's sale gate is durably acknowledged. A timeout, 5xx, unknown gate, stale version or network partition MUST NOT authorize unpublish. A failed Events update after close MUST NOT automatically reopen sales.

#### Scenario: uncertain remote close
- GIVEN a published event and an unavailable Ticketing service
- WHEN Events requests unpublish
- THEN Events keeps published state and refuses to claim completion.

#### Scenario: close success but metadata failure
- GIVEN Ticketing has durably closed sales
- WHEN Events fails before committing metadata transition
- THEN sales remain closed and reconciliation is required before any reopen.

### Requirement: Versioned idempotent service commands

Ticketing SHALL expose authenticated internal gate commands with `event_id`, `expected_version`, `event_revision` and `command_id`. A command ID reused with the same payload MUST return the previously committed result; conflicting payload MUST return conflict. Version mismatch MUST be rejected without side effects. A recorded command/revision MUST NOT permit stale reopening.

#### Scenario: duplicate and reordered open
- GIVEN a gate closed at version 3 and a newer event revision
- WHEN an old open command or a reused command ID with different payload arrives
- THEN Ticketing rejects it without changing the gate.

### Requirement: No false cross-service atomicity

Identity, Events and Ticketing SHALL not share a SQLAlchemy session, schema ownership, foreign key, or distributed database transaction. The coordination SHALL be explicit, recoverable and fail closed.

#### Scenario: Ticketing restart
- GIVEN a close command committed before the HTTP response was lost
- WHEN the service restarts and Events retries or reconciles the command
- THEN the persisted gate state/version decides the result, not the missing HTTP acknowledgement.

### Requirement: Test gates before cutover

The system MUST have integration tests with independent PostgreSQL stores, real HTTP service authentication, lock races (both orders), timeouts, retries, stale versions, crashes and replay behavior before enabling publication/unpublication or routing purchases to H4.

#### Scenario: cutover blocked until integration evidence passes
- GIVEN independently deployed Events and Ticketing services with separate PostgreSQL stores
- WHEN the team evaluates enabling remote publication, unpublication or H4 purchase routing
- THEN the test suite MUST demonstrate both orders of the purchase/close lock race, authenticated internal HTTP, timeout and retry handling, stale-version rejection, crash recovery and idempotent replay
- AND the rollout MUST remain disabled if any required integration test fails or is not executed.
