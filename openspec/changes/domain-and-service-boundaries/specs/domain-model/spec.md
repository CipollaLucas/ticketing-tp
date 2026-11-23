# Domain model and consistency

## ADDED Requirements

### Requirement: Distinguish inventory modes
Each zone SHALL use either numbered seats or a non-numbered capacity, and availability SHALL never be negative.

#### Scenario: General capacity is exhausted
- **WHEN** two transactions try to buy the final available place
- **THEN** exactly one order is confirmed and the other fails without creating tickets.

#### Scenario: Numbered seat is sold twice
- **WHEN** two transactions try to buy the same seat
- **THEN** exactly one active allocation exists and only its order is confirmed.

### Requirement: Atomic and idempotent purchases
Ticketing SHALL commit inventory allocation, order, tickets and the idempotency result in one transaction scoped by customer and operation.

#### Scenario: Request is retried
- **WHEN** a customer repeats the same key and canonical purchase payload
- **THEN** the original order is returned without another inventory decrement.

#### Scenario: Key is reused for different content
- **WHEN** a customer repeats a key with a different canonical payload
- **THEN** the API responds with 409 without modifying the first order.

#### Scenario: One item is unavailable
- **WHEN** an order contains an unavailable item
- **THEN** the entire transaction rolls back, including other items and tickets.

### Requirement: Authorized and idempotent refunds
A refund SHALL affect only an eligible ticket owned by the customer or managed by an administrator, and SHALL release inventory at most once.

#### Scenario: Refund is repeated
- **WHEN** the same eligible ticket is refunded twice
- **THEN** only one refund exists and inventory is released exactly once.

#### Scenario: Customer refunds a foreign ticket
- **WHEN** a customer requests a refund of another customer's ticket
- **THEN** the API responds with 403 without modifying the ticket or inventory.

### Requirement: Explicit service ownership
The design SHALL assign identity to Identity, event publication to Events, and orders, inventory, tickets and refunds to Ticketing.

#### Scenario: Notification delivery fails
- **WHEN** notification delivery fails after a purchase commits
- **THEN** the confirmed purchase remains valid and delivery can be retried independently.
