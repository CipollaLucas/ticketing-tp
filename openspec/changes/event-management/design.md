## Context
The application uses FastAPI/SQLAlchemy/PostgreSQL, but has no event tables/migrations. Ownership depends on authentication-and-roles.

## Proposed decisions
- Event has owner, title, description, venue, starts_at, capacity/status, created/updated timestamps.
- Drafts are not visible on public listings.
- Published events are listed paginated; define whether past events appear in detail versus listing.
- Maintain event status transitions in one service layer.
- Database constraints enforce positive capacities and valid lifecycle values.

## Dependency
Coordinate identity ownership with the auth change. Reserve ticket types and seat inventory for a separate OpenSpec change so the event model does not assume one ticket per event.
