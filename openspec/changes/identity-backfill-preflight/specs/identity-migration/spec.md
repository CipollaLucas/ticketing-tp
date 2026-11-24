# Identity migration safety

## ADDED Requirements

### Requirement: Dry-run-only default
The Identity import tool SHALL never write to either database unless explicitly instructed to apply with a validated source fingerprint.

#### Scenario: Operator audits
- **WHEN** the tool runs without an apply flag
- **THEN** it displays source/pending/unchanged/conflict counts and a fingerprint without copying users or sessions.

### Requirement: Preserve identity and reject conflicts
The import SHALL preserve UUIDs, usernames, password hashes and roles and SHALL reject conflicting existing identities without modifying them.

#### Scenario: Existing username with another UUID
- **WHEN** Identity already has a username with a different UUID
- **THEN** the tool reports a conflict and applies zero writes.

### Requirement: Reject changed snapshots
The import SHALL require a prior fingerprint and reject an apply if the source users have changed.

#### Scenario: Role modified after audit
- **WHEN** a legacy user role changes after the dry-run
- **THEN** an apply using the old fingerprint fails before any write.

### Requirement: Never migrate sessions
The import SHALL NOT copy existing Bearer sessions into the new Identity service.

#### Scenario: Successful user migration
- **WHEN** a user is imported
- **THEN** their UUID and password hash match the legacy account but no session token is created.
