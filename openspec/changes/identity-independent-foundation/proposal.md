## Why
The course requires independent microservices and hexagonal architecture. Identity currently shares the backend process and database with Events and Ticketing.

## What changes
- Add isolated Identity in services/identity: FastAPI, pure domain, ports, use cases, database and crypto adapters.
- Own Alembic migration, Dockerfile, separate PostgreSQL DB and optional Compose overlay.
- Add public identity endpoints and protected internal introspection.
- Test standalone auth and verify legacy core unchanged.

## Limits
No cutover of React, Events or Ticketing in this PR. Cross-service foreign keys and ownership require later incremental migration. Do not claim the system already comprises three microservices.
