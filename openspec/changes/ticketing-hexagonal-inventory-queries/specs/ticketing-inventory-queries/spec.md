# Ticketing hexagonal inventory and queries

## ADDED Requirements

### Requirement: Inventory configuration through a port
The inventory HTTP adapter SHALL delegate creation to an application use case that uses an InventoryPort with no framework dependencies.

#### Scenario: Zone is added
- **WHEN** an authorized event owner configures a valid zone on a future draft event
- **THEN** the zone and seats are committed and the HTTP adapter returns a compatible 201 response.

#### Scenario: Zone conflicts
- **WHEN** an event is published or the zone name already exists
- **THEN** the operation is rejected and no partial inventory is persisted.

### Requirement: Inventory query isolation
The HTTP layer SHALL use an InventoryPort to query public and owner inventory while preserving visibility and authorization.

#### Scenario: Draft event
- **WHEN** the public requests inventory for a draft event
- **THEN** the API returns 404 while the authorized owner may inspect inventory.

### Requirement: Ticket query isolation
Order and ticket retrieval SHALL use a query port and preserve customer privacy and pagination.

#### Scenario: Another customer's order
- **WHEN** a non-admin actor requests another customer's order
- **THEN** the API responds 403 without exposing the receipt.
