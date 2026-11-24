## Why
Complete Issue #31 by replacing SQLAlchemy-in-router inventory configuration and read endpoints with actual hexagonal use cases, ports and adapters. The purchase use case was already extracted in PR #35.

## What changes
- Pure application use cases and ports for zone configuration and inventory views.
- SQLAlchemy inventory adapter preserves event row locks, owner/role checks, constraints, seat availability and atomic persistence.
- Pure order/ticket query port and SQLAlchemy read adapter, preserving authorization and pagination.
- FastAPI remains the inbound HTTP adapter and translates application exceptions.

## Out of scope
Identity and Events remain within the monolith. This PR does not claim the microservices requirement is completed.
