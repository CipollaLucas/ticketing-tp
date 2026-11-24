# Independent Identity microservice

## ADDED Requirements

### Requirement: Independently runnable Identity
Identity SHALL run as an independent FastAPI service with its own database, migration history and Docker image.

#### Scenario: Preview profile
- **WHEN** Identity is started through the optional Compose overlay
- **THEN** it uses its own PostgreSQL database and exposes a health endpoint independently of the legacy backend.

### Requirement: Hexagonal boundaries
The domain and application SHALL have no dependencies on HTTP, ORM or framework adapters.

#### Scenario: Unit tests
- **WHEN** pure Identity tests execute
- **THEN** they require no FastAPI or database.

### Requirement: Secure sessions and introspection
Tokens SHALL be random, stored hashed and checked for expiry, logout and current role.

#### Scenario: Internal introspection
- **WHEN** a request lacks a valid internal service credential
- **THEN** no principal is returned, regardless of the Bearer token.

### Requirement: Legacy compatibility during migration
Existing frontend, backend and purchase transactions SHALL remain unchanged until an explicit tested cutover.

#### Scenario: Default Compose
- **WHEN** only the current Compose stack runs
- **THEN** legacy Identity/Events/Ticketing APIs are unchanged.
