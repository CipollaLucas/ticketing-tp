## Why
Issue #31 requires a real hexagonal boundary for purchase, not only pure hashing and unused Protocols. The legacy FastAPI purchase endpoint currently coordinates SQLAlchemy directly.

## What changes
- Move atomic allocation, persistence and row locks to a concrete SQLAlchemy outbound adapter.
- Introduce a purchase application use case depending only on PurchaseUnitOfWorkPort.
- Map domain/application errors to HTTP responses in the FastAPI inbound adapter.
- Preserve public request/response, 201/200 replay, 403/404/409/422, PostgreSQL locking and rollback behavior.
- Verify behavior with fake adapter tests and full existing PostgreSQL concurrency suite.

## Out of scope
Identity and Events still share the monolith and database; this change does NOT claim microservice compliance.
