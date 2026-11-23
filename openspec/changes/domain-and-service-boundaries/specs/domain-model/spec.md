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

### Requirement: Administratively reviewed refunds
In Stage III, a customer SHALL request a refund of their own eligible ticket as pending. Only administrators SHALL approve or reject it. Only approval SHALL invalidate the ticket and release inventory once, atomically recording the decision and reviewer.

#### Scenario: Customer submits a request
- **WHEN** a customer requests a refund for an eligible ticket they own
- **THEN** a pending request is created without changing the ticket or inventory.

#### Scenario: Administrator approves repeatedly
- **WHEN** an administrator approves an eligible pending request and repeats the approval
- **THEN** the decision is recorded and inventory is released exactly once.

#### Scenario: Administrator rejects
- **WHEN** an administrator rejects a pending request with a reason
- **THEN** the rejection and reviewer are recorded without changing ticket or inventory.

#### Scenario: Customer attempts to decide
- **WHEN** a customer or event owner attempts to approve or reject a refund
- **THEN** the API responds with 403 without mutations.

#### Scenario: Concurrent opposite decisions
- **WHEN** approval and rejection race for the same pending request
- **THEN** one terminal decision wins and the conflicting decision receives 409.

#### Scenario: Customer requests a foreign refund
- **WHEN** a customer requests a refund of another customer's ticket
- **THEN** the API responds with 403 without modifying the ticket or inventory.

### Requirement: Explicit service ownership
The design SHALL assign identity to Identity, event publication to Events, and orders, inventory, tickets and refunds to Ticketing.

#### Scenario: Notification delivery fails
- **WHEN** notification delivery fails after a purchase commits
- **THEN** the confirmed purchase remains valid and delivery can be retried independently.
