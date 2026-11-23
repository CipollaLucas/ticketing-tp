# Event management

## ADDED Requirements

### Requirement: Owners manage their own events
The system SHALL permit authorized event owners to create and update their own draft events.

#### Scenario: Owner creates a draft
- **WHEN** an authorized event owner submits valid event information
- **THEN** a draft event belonging to that owner is created.

### Requirement: Publish valid events
The system SHALL only publish events that meet documented publication requirements.

#### Scenario: Incomplete draft is published
- **WHEN** an owner attempts to publish an incomplete draft
- **THEN** the system rejects publication without changing its status.

### Requirement: Public catalog visibility
The system SHALL expose published events via paginated public APIs and hide drafts.

#### Scenario: Public event listing
- **WHEN** an unauthenticated visitor lists events
- **THEN** the response contains only eligible published events with pagination information.
