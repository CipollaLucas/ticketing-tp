# Frontend core experience

## ADDED Requirements

### Requirement: Discover events
The frontend SHALL display available published events and let visitors access event detail.

#### Scenario: Empty catalog
- **WHEN** the events API returns no events
- **THEN** the interface displays an explicit empty state and does not imply that tickets are on sale.

### Requirement: Role-specific navigation
The frontend SHALL expose navigation options appropriate to the current authenticated role.

#### Scenario: Customer signs in
- **WHEN** a customer signs in successfully
- **THEN** customer navigation is available and administrative controls are not displayed.

### Requirement: Honest demo states
The frontend SHALL distinguish functional purchase actions from mockups or unavailable integrations.

#### Scenario: Purchase API not yet implemented
- **WHEN** the user opens a purchase mockup before backend purchase exists
- **THEN** the interface indicates demo/unavailable state and does not claim a ticket was purchased.
