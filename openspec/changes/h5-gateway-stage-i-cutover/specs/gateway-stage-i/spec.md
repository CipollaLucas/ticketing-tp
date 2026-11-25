# H5 Gateway Stage I requirements

## Requirement: Browser-facing API routes have a single service owner
The system SHALL provide one opt-in public /api/v1 entrypoint routing to Identity, Events and Ticketing without routing any Identity-authenticated request to Legacy.

### Scenario: Valid public route
- **WHEN** a browser calls a documented Stage I public route via the Gateway
- **THEN** the responsible service handles the request and preserves its published response contract.

### Scenario: Unsupported or internal route
- **WHEN** a browser requests an unsupported path or an internal service endpoint
- **THEN** the Gateway rejects it without forwarding it to Legacy or exposing internal credentials.

## Requirement: Independent deployment is demonstrable
The system SHALL run independent backend processes with distinct PostgreSQL persistence and migrations.

### Scenario: Legacy unavailable
- **WHEN** Legacy is offline during an isolated Stage I UAT
- **THEN** the full three-role journey can complete through the Gateway, or the unmet feature is recorded explicitly as a failing acceptance criterion.

## Requirement: Financial and inventory safety survives routing and failures
The Gateway SHALL preserve service-side authorization, bounded timeouts and idempotency controls; it SHALL NOT assert payment was captured merely because a purchase is confirmed.

### Scenario: Concurrent last ticket
- **WHEN** two buyers compete for a single remaining unit
- **THEN** at most one new confirmed allocation occurs and inventory is nonnegative.

### Scenario: Ambiguous timeout
- **WHEN** a command commits but its response is lost
- **THEN** a retry with the same identifier does not apply the effect twice, and the result is reconciled or safely rejected.

### Scenario: Dependency outage
- **WHEN** Identity, Events or Ticketing is unavailable during a protected mutation
- **THEN** the request fails closed without minting an unauthorized order.

## Requirement: HTTP audit includes timing and outcome
Each handled request SHALL be observable with method, route, status, monotonic duration and correlation identifier; authentication failures SHALL be included without leaking sensitive values.

### Scenario: Authenticated and rejected calls
- **WHEN** a successful request and an invalid-token request are made through the Gateway
- **THEN** both have correlated outcome and duration records at each relevant service hop and neither record includes secrets.

## Requirement: Cutover is reversible and explicitly authorized
The system SHALL keep full Gateway/cutover disabled by default and SHALL provide a tested runbook for data migration, backup/restore and safe rollback.

### Scenario: No approval
- **WHEN** the new environment is built without an explicit cutover decision
- **THEN** Legacy traffic and active data are unchanged and no commercial feature is activated.
