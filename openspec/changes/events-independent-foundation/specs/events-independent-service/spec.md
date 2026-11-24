# Independent Events Service

## ADDED Requirements

### Requirement: Independently deployable Events service
Events SHALL run as a separate process/image with independent configuration, healthcheck, PostgreSQL database and Alembic migrations.

#### Scenario: Independent startup
- **WHEN** only Events and its own database are started
- **THEN** the service starts and reports its own health without Legacy, React or Ticketing database access.

### Requirement: Hexagonal boundaries
Business validation and transition rules SHALL be independent of HTTP, ORM and infrastructure packages. Use cases SHALL depend on ports rather than concrete adapters.

#### Scenario: Domain unit tests
- **WHEN** domain tests execute without PostgreSQL or network
- **THEN** event rules are testable without importing FastAPI/SQLAlchemy.

### Requirement: Service data ownership
Events SHALL own its own event metadata/status and store owner UUIDs without FK or SQL joins to Identity or Ticketing.

#### Scenario: Foreign identity
- **WHEN** Events persists an owner UUID
- **THEN** no SQL relationship or access to another service database is necessary.

### Requirement: Preserve existing runtime during extraction
H3 SHALL NOT reroute the existing React /api/v1 endpoints or allow Events preview to control Legacy purchases.

#### Scenario: Opt-in preview disabled
- **WHEN** the independent service is not started
- **THEN** existing Legacy demo API and checkout behavior remain unchanged.

### Requirement: Safe publication transition
Events SHALL NOT allow a remote status change that could race against Ticketing sales until an explicit serializing protocol is validated.

#### Scenario: Attempt remote unpublish
- **WHEN** sale-state coordination has not been approved
- **THEN** an unsafe unpublish must be rejected and must not silently permit a concurrent sale.

### Requirement: Fail-closed protected operations
Events SHALL use an authenticated internal Identity contract with bounded timeouts. Failed validation SHALL NOT grant additional permissions.

#### Scenario: Identity unavailable
- **WHEN** a protected action requires introspection and Identity is unreachable
- **THEN** the action is denied or unavailable without committing a mutation.
