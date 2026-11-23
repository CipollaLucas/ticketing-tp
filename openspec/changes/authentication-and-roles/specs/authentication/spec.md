# Authentication and roles

## ADDED Requirements

### Requirement: Authenticate users
The system SHALL authenticate registered users before granting access to protected endpoints.

#### Scenario: Unauthenticated request
- **WHEN** a client requests a protected endpoint without valid credentials
- **THEN** the API responds with 401 and does not disclose protected data.

### Requirement: Role-based authorization
The system SHALL distinguish administrator, event owner, and customer roles, enforcing resource ownership.

#### Scenario: Customer attempts administrative action
- **WHEN** an authenticated customer invokes an administrator-only operation
- **THEN** the API responds with 403 and performs no mutation.

#### Scenario: Owner modifies another owner's event
- **WHEN** an event owner attempts to modify an event owned by a different user
- **THEN** the API responds with 403 and performs no mutation.

### Requirement: Secure registration defaults
Public registration SHALL never allow self-assignment of an elevated role.

#### Scenario: Client includes admin role in registration
- **WHEN** a public registration includes an administrator role request
- **THEN** the resulting account remains a customer or the request is rejected.


### Requirement: Revocable expiring sessions
The system SHALL issue opaque bearer sessions, store only token hashes and reject expired or revoked sessions.

#### Scenario: Session is logged out
- **WHEN** a user logs out with a valid session token
- **THEN** that session is revoked and subsequent protected requests with it receive 401.

#### Scenario: Session expires
- **WHEN** a session reaches its UTC expiry
- **THEN** protected requests using that token receive 401.

### Requirement: Secure password storage
The system SHALL store Argon2 password hashes and never include credentials or password hashes in API responses or validation errors.

#### Scenario: Password fails validation
- **WHEN** registration receives a password with an invalid length
- **THEN** the API returns 422 without echoing that password.

### Requirement: Safe role updates
Only current administrators SHALL update other users' roles; serialized role changes SHALL recheck the actor's current role before mutation.

#### Scenario: Administrators concurrently demote each other
- **WHEN** two administrators attempt to demote each other concurrently
- **THEN** one succeeds and the other is denied without removing the remaining administrator.
