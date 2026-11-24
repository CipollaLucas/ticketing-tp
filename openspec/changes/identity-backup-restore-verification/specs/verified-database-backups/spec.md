# Independent verified PostgreSQL backups

## ADDED Requirements

### Requirement: Two separate database archives
The backup tool SHALL create a distinct local binary PostgreSQL archive for legacy and standalone Identity without modifying either source.

#### Scenario: Both databases active
- **WHEN** the host executes the backup verification command
- **THEN** it saves two custom-format dumps and calculates independent SHA-256 hashes.

### Requirement: Restore is isolated and temporary
Each archive SHALL be restored only into a newly created ephemeral PostgreSQL container without a network or published ports.

#### Scenario: Successful restore
- **WHEN** pg_restore completes in a disposable database
- **THEN** critical table counts match the source and the temporary container is removed.

### Requirement: Fail closed
The process SHALL never claim verified recovery if an archive fails, a count differs or an isolated restore is unavailable.

#### Scenario: Restore failure
- **WHEN** pg_restore exits with a failure
- **THEN** the tool exits nonzero, retains existing dump files, and does not modify live PostgreSQL.

### Requirement: Backup privacy
Backups and manifests SHALL be ignored by Git and contain no cleartext DB passwords or Bearer tokens.

#### Scenario: Local execution
- **WHEN** a backup is produced
- **THEN** it remains under the developer-selected local directory and is not committed to the repository.
