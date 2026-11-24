# Hexagonal boundaries and independent services

## ADDED Requirements

### Requirement: Pure domain rules
All backend business domain modules SHALL avoid importing FastAPI, SQLAlchemy, Pydantic, HTTP libraries and concrete persistence adapters.

#### Scenario: Canonical purchase identity
- **WHEN** a purchase has its zone items or seats in different orders
- **THEN** its canonical request hash remains stable without any FastAPI or ORM import.

#### Scenario: Reuse key with different payload
- **WHEN** a previously stored hash differs from the proposed hash
- **THEN** a framework-independent domain exception rejects the replay.

### Requirement: Independent deployable services
Identity, Events and Ticketing SHALL each have an independently launchable API, dedicated storage schema/database, own migrations and a health endpoint, and SHALL NOT directly query another service's tables.

#### Scenario: Services started separately
- **WHEN** the Compose profile is launched
- **THEN** three independently addressable services start and health checks pass.

### Requirement: Maintain atomic ticketing
All stock decrements, orders, order items, issued tickets and idempotency records SHALL remain committed together under PostgreSQL concurrency protections.

#### Scenario: Last seat race
- **WHEN** two customers compete concurrently for one remaining seat
- **THEN** exactly one order succeeds, the other is rejected and no duplicate seat ticket is created.

### Requirement: Safe cross-service business state
The architecture SHALL prevent a remote event visibility/state transition from racing a ticket purchase into inconsistent confirmed sales.

#### Scenario: Event unpublish overlaps a purchase
- **WHEN** unpublication and purchase race across services
- **THEN** the documented coordination protocol serializes the transitions or rejects unsafe operations; a single isolated GET check is insufficient.

### Requirement: Failure isolation and authentication
Protected services SHALL fail closed when Identity is unavailable and sales SHALL not confirm from an unverified Events state.

#### Scenario: Identity unavailable
- **WHEN** Identity cannot introspect a Bearer token
- **THEN** protected services reject requests instead of treating the user as authenticated.
