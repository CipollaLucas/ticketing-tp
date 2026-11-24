# Pre-cutover identity consistency gate

An offline read-only checker compares the current legacy and standalone Identity databases using independent connections. Its source snapshot uses PostgreSQL REPEATABLE READ READ ONLY when available.

The check establishes:
1. Every legacy user UUID appears in the independent Identity DB.
2. Username, display name, role and password hash match exactly for those UUIDs.
3. Every owner ID in Events and every customer ID in Orders can be resolved in independent Identity, even if legacy data is already inconsistent.
4. Legacy sessions remain in the old DB and are not copied by the checker.

No import, update, delete, DDL, session transfer or login switchover is performed. Empty legacy user datasets cannot be declared ready. Extra Identity accounts are permitted but must be reviewed for authority and test data before cutover.

A positive check means **ready for manual architecture review only**. Runtime switch still needs event/stock coordination, remote role authorization under locks, schema isolation and a tested rollback plan.
