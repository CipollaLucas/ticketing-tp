# Read-only identity canary

## ADDED Requirements

### Requirement: Disabled by default
The canary SHALL be unavailable unless deliberately enabled with a dedicated environment setting.

#### Scenario: Normal deployment
- **WHEN** the backend starts without IDENTITY_CANARY_ENABLED
- **THEN** the canary returns 404 and existing auth endpoints remain unchanged.

### Requirement: Remote and local identity must agree
The canary SHALL grant a diagnostic success only for a valid current Identity Bearer session with a matching Legacy UUID, username and role.

#### Scenario: Migrated account
- **WHEN** Identity authenticates an account and Legacy confirms its UUID, username and role
- **THEN** the read-only canary reports both checks successful.

#### Scenario: Role drift
- **WHEN** remote and local roles differ
- **THEN** the canary rejects the request without updating either database.

### Requirement: Fail closed
The canary SHALL not fall back to local sessions if Identity is unavailable, revokes a token or responds invalidly.

#### Scenario: Identity disconnected
- **WHEN** remote introspection times out
- **THEN** the canary returns an unavailable status and does not grant authorization.

### Requirement: No write authority
A successful canary SHALL NOT create sessions, grant purchase permissions, modify accounts, or remove foreign keys.

#### Scenario: Successful canary
- **WHEN** a customer identity passes
- **THEN** purchases and event mutations still use the existing authorization until a separate cutover is approved.
