# Frontend React Demo

## ADDED Requirements

### Requirement: React-based navigable preview
The frontend SHALL render catalog, event detail, access/registration, checkout, sample tickets, event-owner and administrator views without requiring the backend to serve event inventory.

#### Scenario: Visitor browses the demo
- **WHEN** a visitor opens the frontend
- **THEN** a sample event catalog with clear fictitious-data indication is displayed.

### Requirement: No false transaction or authentication
The frontend SHALL never claim an actual purchase, emitted ticket, login or role change in demo mode.

#### Scenario: Visitor simulates checkout
- **WHEN** the visitor submits the checkout preview
- **THEN** a notice explains that no payment, inventory reservation or ticket emission occurred.

### Requirement: Accessible catalog state feedback
The frontend SHALL offer visible loading, empty and error mock states, and basic keyboard navigation.

#### Scenario: Demo API failure state
- **WHEN** the preview is switched to error
- **THEN** an explicit non-success message is displayed without inventing event availability.
