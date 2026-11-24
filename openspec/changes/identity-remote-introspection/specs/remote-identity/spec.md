# Cross-service Identity

## ADDED Requirements

### Requirement: Remote Identity port
Ticketing application SHALL express remote Identity verification via an abstract port without importing HTTP or ORM.

#### Scenario: Valid customer
- **WHEN** Identity answers 200 with a valid principal and role
- **THEN** the adapter returns a typed principal with that role.

### Requirement: Fail closed on invalid or unavailable Identity
The adapter SHALL deny authentication for missing, expired and rejected tokens and treat infrastructure failures as unavailable, never as an authenticated session.

#### Scenario: Identity unavailable
- **WHEN** the upstream times out or disconnects
- **THEN** no authenticated principal is returned.

#### Scenario: Internal secret denied
- **WHEN** Identity returns 403 for an invalid service credential
- **THEN** no authenticated principal is returned.

### Requirement: End-to-end session revocation
The integration smoke SHALL verify login, HTTP introspection and logout against the independent Identity database and API.

#### Scenario: Revoked token
- **WHEN** a logged-in session is revoked
- **THEN** subsequent Ticketing-to-Identity introspection rejects the same token.
