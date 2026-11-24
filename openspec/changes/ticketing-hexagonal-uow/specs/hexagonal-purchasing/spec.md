# Hexagonal purchase use case

## ADDED Requirements

### Requirement: Purchase use case depends on ports
The purchasing application SHALL coordinate business actions only through a PurchaseUnitOfWorkPort and pure domain policies.

#### Scenario: New purchase
- **WHEN** a valid new idempotency key is submitted
- **THEN** the use case locks customer, checks replay, allocates, reads receipt and commits once.

#### Scenario: Repeated purchase
- **WHEN** an existing key matches the canonical payload hash
- **THEN** the use case returns the prior order without new stock allocation.

#### Scenario: Allocation failure
- **WHEN** persistence or ticket emission fails
- **THEN** the use case rolls back and does not commit.

### Requirement: Preserve PostgreSQL concurrency
The adapter SHALL retain customer/event/zone row locks and atomic order, ticket and inventory persistence.

#### Scenario: Concurrent final seat
- **WHEN** two customers request one remaining seat
- **THEN** exactly one order succeeds without double selling the seat.
