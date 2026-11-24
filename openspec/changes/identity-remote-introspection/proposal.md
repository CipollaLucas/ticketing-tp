## Why
Issue #32 needs actual service-to-service authentication rather than shared tables. Identity is independently runnable, but Events/Ticketing still authenticate with their legacy ORM tables.

## What changes
- Add a pure `IdentityPort` and principal snapshot to the Ticketing application layer.
- Implement an outbound HTTP adapter for Identity introspection with mandatory internal service credential, bounded timeout, strict responses, no redirects and fail-closed semantics.
- Connect the *optional* Compose overlay to the real Identity hostname for server-side integration only.
- Add unit tests for HTTP status, errors, timeout, malformed responses and revocation plus an integration smoke program making real HTTP calls between containers.

## Out of scope
No switch of existing user sessions, React or purchases to remote Identity yet. Legacy User and Event/Order foreign keys are not removed or copied. This step only proves the transport contract; the application will use it for authorization after the ownership/data migration.
