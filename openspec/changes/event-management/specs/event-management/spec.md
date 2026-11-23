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

### Requirement: Event writes use authenticated ownership
The system SHALL derive draft ownership from the authenticated user and reject
client-supplied owner IDs or status. Customers SHALL receive 403 and missing or
invalid credentials SHALL receive 401. Administrators SHALL be allowed to manage
all events; other event owners SHALL only manage their own events.

#### Scenario: Another owner attempts an update
- **WHEN** an event owner attempts to edit another owner's event
- **THEN** the system returns 403 without changing the event.

#### Scenario: Administrator manages an existing event
- **WHEN** an administrator updates another owner's valid draft
- **THEN** the update succeeds without changing ownership.

### Requirement: Draft updates preserve valid metadata
The system SHALL accept only documented event fields, timezone-aware dates and
an end after the start. Creating or rescheduling an event SHALL require a future
start. Updating a published event SHALL return 409 until it is unpublished.

#### Scenario: Partial update makes the date interval invalid
- **WHEN** an authorized owner patches an end date before the stored start date
- **THEN** the system returns 422 and preserves all stored event fields.

### Requirement: Catalog pagination is deterministic
The system SHALL list future published events ordered by start_at and id, with
limit from 1 to 100, nonnegative offset and total matching the filtered set. Public
detail SHALL expose published past events but SHALL return 404 for drafts.

#### Scenario: Visitor requests a page beyond the last event
- **WHEN** a visitor supplies a valid offset beyond the last matching event
- **THEN** the response is 200 with empty items and the filtered total.

#### Scenario: Owner lists private drafts
- **WHEN** an event owner lists the owner catalog
- **THEN** the response includes only that owner's events, including drafts.

### Requirement: Event storage has a reversible migration
The system SHALL create event storage after the identity migration and SHALL
support downgrade without dropping identity data.

#### Scenario: Event migration is reversed and reapplied
- **WHEN** the event migration is upgraded, downgraded to identity and upgraded again
- **THEN** event tables match ORM metadata and preexisting identity data survives.

### Requirement: Metadata publication does not require inventory
The system SHALL allow publication of valid event metadata without zones in this
increment. Publication SHALL NOT claim ticket availability or enable purchasing.
Publishing SHALL require a nonempty description and valid future start. Repeating
publish or unpublish in its current state SHALL return 200 without mutating it.

#### Scenario: Complete event has no configured zones
- **WHEN** an authorized owner publishes complete metadata with valid future dates and no zones
- **THEN** the event becomes published and visible in the public catalog without inventory fields.

#### Scenario: Incomplete description prevents publication
- **WHEN** an authorized owner publishes a draft whose description is empty
- **THEN** the system returns 422 and the event remains draft and hidden.

### Requirement: Concurrent event mutations respect committed state
The system SHALL serialize mutations of one event in PostgreSQL and recheck
status and authorization after waiting for a concurrent writer.

#### Scenario: Another writer publishes before a waiting draft update
- **WHEN** a draft update waits for a concurrent publication to commit
- **THEN** it returns 409 and preserves the published event without applying the edit.

#### Scenario: Actor loses permissions while waiting
- **WHEN** an event mutation waits and the actor's owner role is revoked before the lock is released
- **THEN** it returns 403 and preserves the event.
