## Architectural boundaries

- **Inbound:** `app/purchasing.py` handles Pydantic, authentication dependency, HTTP status and serializes order snapshots into OrderResponse.
- **Application:** `app/ticketing_core/application/purchase_tickets.py` coordinates lock → idempotency lookup → allocate/read → commit. It imports only port types and pure purchase domain rules.
- **Port:** `app/ticketing_core/application/ports.py` defines `PurchaseUnitOfWorkPort` and immutable order snapshots. The application does not use ORM objects.
- **Outbound:** `app/ticketing_core/adapters/outbound/sqlalchemy_purchase.py` locks User/Event/Zone in the same order as before, updates stock, writes order/items/tickets and reads receipt before commit.

## Invariants
1. Existing idempotency key lookup takes place under the locked customer row.
2. All stock decrement, ticket issue, order insert and receipt verification occur in one transaction.
3. Any exception triggers rollback; HTTP 409 SQL IntegrityError maps at inbound edge.
4. No HTTP/framework or SQLAlchemy dependency from the domain or application use case.
5. Authorization, event-sale state, zone constraints, price/currency and last seat rules unchanged.

## Risk
Preserve order of SELECT FOR UPDATE and SQL save sequence. Existing PostgreSQL concurrent tests, including rollback injection, are the regression gate. No separate service boundary exists yet.
