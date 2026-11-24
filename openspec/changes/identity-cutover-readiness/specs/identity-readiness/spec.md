# Independent Identity cutover readiness

## ADDED Requirements

### Requirement: Read-only reference audit
The migration readiness check SHALL inspect but never modify legacy or independent Identity databases.

#### Scenario: Audit without migration
- **WHEN** legacy users are not imported
- **THEN** the checker reports missing UUIDs and exits without writing any record.

### Requirement: Verify every referenced external identity
The readiness checker SHALL verify that all event owners and order customers exist in Identity regardless of local foreign key integrity.

#### Scenario: Order references unknown UUID
- **WHEN** an order references a customer ID not present in independent Identity
- **THEN** the checker reports the missing reference and must not mark ready.

### Requirement: Preserve user identity attributes
The checker SHALL compare UUID, username, display name, role and password hash, and SHALL reject mismatches.

#### Scenario: Role drift
- **WHEN** Identity role differs from the legacy role for a user ID
- **THEN** the checker reports a mismatch.

### Requirement: Readiness is not cutover
Successful consistency auditing SHALL NOT change runtime authorization, copy sessions, remove foreign keys or activate microservice traffic.

#### Scenario: All IDs match
- **WHEN** every ID and account matches
- **THEN** the result is ready for manual review only, not an automated deployment.
