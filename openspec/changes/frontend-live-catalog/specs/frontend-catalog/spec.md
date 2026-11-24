# Real catalog integration

## ADDED Requirements

### Requirement: Fetch only public published events
The frontend SHALL query the public events API and render only validated published event metadata.

#### Scenario: API returns a published event
- **WHEN** the public API responds with a published event page
- **THEN** the frontend displays the event's real title, date and venue without a sale action.

### Requirement: Safe empty and failure states
The frontend SHALL distinguish loading, empty, error and missing-detail responses.

#### Scenario: No published events exist
- **WHEN** the API returns an empty page
- **THEN** the frontend shows an empty state without substituting fictitious cards.

#### Scenario: Detail is unavailable
- **WHEN** a selected event returns HTTP 404
- **THEN** the frontend shows an unavailable state rather than fictional event details.

### Requirement: Demo data separation
The frontend SHALL keep example events and example prices exclusively in an explicitly selected demo mode.

#### Scenario: Visitor starts in real mode
- **WHEN** the application loads
- **THEN** only real API results are eligible for display and sale remains disabled.
