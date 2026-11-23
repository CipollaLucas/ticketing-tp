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
