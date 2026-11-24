# Functional Stage I web

## ADDED Requirements

### Requirement: Real identity
The frontend SHALL authenticate against the identity API and keep access credentials only in volatile memory.

#### Scenario: Customer login
- **WHEN** a customer logs in with valid credentials
- **THEN** the API returns a token, the frontend fetches the actual role, and the purchase workspace becomes available.

### Requirement: Real event ownership
An event owner SHALL be able to create future draft event metadata, configure general or numbered inventory, and publish it using authorized API calls.

#### Scenario: Event publication
- **WHEN** an owner publishes a valid draft with inventory
- **THEN** the published event is eligible to appear in the real catalog.

### Requirement: Simulated purchase without actual payment
A customer SHALL be able to purchase real test tickets through the backend and view emitted ticket identities. The frontend SHALL clearly disclaim financial settlement.

#### Scenario: Purchase confirmation
- **WHEN** the server returns HTTP 201 with an Order and Ticket list
- **THEN** the frontend displays confirmed order details; it never claims a bank payment.

### Requirement: Safe retry and overselling feedback
The frontend SHALL reuse Idempotency-Key on retry of an unchanged payload and SHALL display capacity conflicts without claiming success.

#### Scenario: Replay
- **WHEN** a request is replayed with the same key and payload
- **THEN** the server may return HTTP 200 with the same order and Idempotent-Replayed true.

#### Scenario: No capacity
- **WHEN** stock is exhausted
- **THEN** HTTP 409 is rendered as an error without creating a confirmed UI order.
