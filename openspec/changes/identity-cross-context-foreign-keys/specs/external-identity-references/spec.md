# Independent identity references

## ADDED Requirements

### Requirement: Event and order IDs point to external identities
Events.owner_id and Orders.customer_id SHALL retain UUIDs and business constraints without foreign keys to Legacy users.

#### Scenario: Existing orders
- **WHEN** Alembic migrates the current schema
- **THEN** all existing order and event identifiers are preserved.

### Requirement: Legacy sessions stay intact
The migration SHALL preserve the users and auth_sessions schema and data.

#### Scenario: Existing sessions
- **WHEN** the migration completes
- **THEN** legacy logins and sessions are not copied or removed.

### Requirement: Reversible transition
The migration SHALL recreate local foreign keys during downgrade if referenced UUIDs all exist locally.

#### Scenario: Rollback to previous migration
- **WHEN** the operator downgrades with valid legacy user references
- **THEN** both foreign keys are restored without deleting orders.

### Requirement: No authorization cutover
Removing foreign keys SHALL NOT enable writes using unverified remote tokens.

#### Scenario: Same backend
- **WHEN** schema changes are installed
- **THEN** existing auth, role and transaction logic remain unchanged.
