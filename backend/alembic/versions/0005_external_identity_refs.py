"""Decouple event owner and order customer IDs from the legacy users table.

Revision ID: 0005_external_identity_refs
Revises: 0004_purchasing

The UUID columns and all business constraints remain unchanged. The migration
does not drop any users, sessions, events, orders, order items or tickets.
"""
import sqlalchemy as sa

from alembic import op

revision = "0005_external_identity_refs"
down_revision = "0004_purchasing"
branch_labels = None
depends_on = None

# SQLite uses unnamed FKs, so Alembic's batch reflection must assign names.
NAMES = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _legacy_fk(table: str, column: str) -> str:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    matches = [
        constraint for constraint in inspector.get_foreign_keys(table)
        if constraint["referred_table"] == "users"
        and constraint["constrained_columns"] == [column]
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one legacy FK on {table}.{column}")
    return matches[0]["name"] or f"fk_{table}_{column}_users"


def upgrade() -> None:
    # Keep legacy user/session table intact; only remove *cross-context* FKs.
    for table, column in (("events", "owner_id"), ("orders", "customer_id")):
        constraint_name = _legacy_fk(table, column)
        with op.batch_alter_table(table, naming_convention=NAMES) as batch:
            batch.drop_constraint(constraint_name, type_="foreignkey")


def downgrade() -> None:
    # Rollback is allowed only when every UUID resolves to a local user.
    # SQL integrity checks on the recreated FK fail if any identity is missing.
    for table, column in (("orders", "customer_id"), ("events", "owner_id")):
        with op.batch_alter_table(table, naming_convention=NAMES) as batch:
            batch.create_foreign_key(
                f"fk_{table}_{column}_users", "users", [column], ["id"],
            )
