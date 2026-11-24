# ADR-0012 — Transactional purchase authority during Stage I

Status: Accepted for the Stage I migration; Identity write cutover remains deferred.

## Decision

Use option C from ADR-0011 for critical purchases. The Legacy/Ticketing PostgreSQL `users` row remains the **authoritative role row for purchase authorization** during this transitional phase. `SqlAlchemyPurchaseUnitOfWork.lock_customer` must lock that row with `SELECT ... FOR UPDATE` and check the current `customer` role before either idempotency lookup or inventory allocation. The resulting order/ticket/stock changes and the role check occur in a single local transaction. A role update using the same transaction boundary must serialize against the customer lock.

The independent Identity Service continues to run for its own account/session demonstrations, introspection and read-only canary. It is NOT the business write authorization authority. Remote tokens must NOT enter the Legacy purchase endpoints. The separate Identity role may diverge from Legacy: this arrangement does not provide immediate revocation from Identity; only a change to the Legacy authoritative role row orders against purchases. The team must explicitly handle synchronization and eventual ownership transfer before remote cutover.

## Invariants

1. A completed Legacy role demotion before the customer lock is acquired denies checkout with 403, without orders, tickets or inventory changes.
2. An already-running purchase that acquired the lock first may finish before a subsequent Legacy role update; that update waits. The serialization order is the lock order, not request arrival time.
3. An idempotent replay must recheck the active Legacy role first; a revoked account cannot replay past its current permission check.
4. A denied or failed transaction rolls back and does not consume an idempotency key. A later authorized retry may use that key.
5. A successful replay returns the original order without double-selling inventory.
6. Identity outages do not turn remote authentication into a fallback route for critical writes. Legacy write authentication is explicitly unchanged.

## Evidence and release policy

`backend/tests/test_purchase_authority_contract.py` tests actual PostgreSQL row-lock waiting, role revocation, stock/order rollback, replay denial and successful retry using disposable schemas. Tests deliberately do not access either user's active database. Existing purchase concurrency tests and the full CI suite must also remain green.

This is a preservation of the current transactional authority, not physical service decomposition, distributed atomic authorization, or a production-ready migration. The remote Identity cutover stays blocked until a separate ADR specifies account/role synchronization, single ownership, migration sequencing, failure behavior and an operational rollback.

## Rollback

This increment changes no runtime code, schemas, deployments, or persistent data. Reverting its test/docs commit does not change system behavior. Do not drop Legacy users or auth_sessions based on this ADR.