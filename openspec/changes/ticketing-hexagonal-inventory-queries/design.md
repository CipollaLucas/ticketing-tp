## Hexagonal slices

HTTP /api/v1/events/{event_id}/zones and inventory endpoints → configure_zone / view_inventory → InventoryPort → SqlAlchemyInventoryAdapter.

HTTP /orders/{id} and /me/tickets → get_order / get_my_tickets → TicketQueriesPort → SqlAlchemyTicketQueries.

Transport DTOs remain Pydantic in routers. Read models are immutable dataclasses in the application; they are converted at the inbound boundary. The application layer must import neither FastAPI nor ORM.

## Invariants

- Zone creation takes event FOR UPDATE lock before checking draft status and role. It commits zone and numbered seats atomically, and unique constraints reject duplicate names under race.
- Public inventories are visible only for published events; owner inventory checks ownership.
- Seat availability comes from actual sold Ticket rows; general available comes from the stored capacity balance.
- Query pagination and owner/customer authorization retain established HTTP behavior.
- Inventory views are advisory; only PurchaseUnitOfWork commits sales.
- PostgreSQL tests for duplicate creation, last place and replay remain mandatory.
