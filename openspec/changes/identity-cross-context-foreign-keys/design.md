# Cross-context reference decoupling

Identity owns canonical accounts. Events and Ticketing retain external identity UUIDs rather than relational foreign keys to the Legacy users table. The application continues enforcing the existing Legacy authentication until a separate tested cutover.

Migration 0005 discovers PostgreSQL FK names with SQLAlchemy inspection and uses Alembic batch mode with a naming convention for unnamed SQLite FKs. Downgrade recreates the previous constraints only if all referenced UUIDs resolve locally. Users and auth_sessions are untouched; event and order IDs, stock and tickets remain unchanged.

Removing FKs does not establish remote authentication: protected writes still require authenticated principals and role rechecks during transaction locks. That rollout is a separate milestone.
