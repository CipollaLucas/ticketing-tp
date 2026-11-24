# Identity architecture foundation

## Hexagonal dependency flow
HTTP adapters to application use cases to outbound ports, implemented by SQLAlchemy and cryptography adapters. Domain and application never import FastAPI, Pydantic, SQLAlchemy or other backend modules.

## Ownership
identity-db owns users and sessions. New Identity service is independently executable with its own migrations. Legacy backend still uses the legacy users table in the existing stack, unchanged by this optional profile.

## Security
Opaque 32-byte random tokens stored hashed SHA-256, Argon2 for passwords. Internal introspection requires user Bearer and X-Internal-Service-Token supplied by environment, with constant-time comparison. Identity returns role/profile data only; absent/invalid sessions fail closed.

## Next migration
Existing Event.owner_id and Order.customer_id point to legacy user rows by DB FK. A later cutover must remove cross-service FK dependencies and replace direct ORM lookups with secure internal HTTP adapters, handling request timeout, administrator revocation and failures. Do not mix this change with a data migration.
