"""Decouple external owner/customer UUIDs from legacy users.

Revision ID: 0005_external_identity_refs
Revises: 0004_purchasing

Preserves all data, business constraints and the local auth/session tables.
"""
from contextlib import contextmanager

import sqlalchemy as sa

from alembic import op

revision = "0005_external_identity_refs"
down_revision = "0004_purchasing"
branch_labels = None
depends_on = None

NAMES = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


@contextmanager
def sqlite_batch_rebuild():
    """SQLite requires FKs off while recreating a table referenced by child tables.

    Restore enforcement and perform an explicit integrity check afterwards.
    Production PostgreSQL always keeps all FKs enabled.
    """
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        yield
        return
    previous = int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one())
    if previous:
        # SQLite refuses to change PRAGMA foreign_keys within an open transaction.
        # SQLite Alembic runs non-transactional DDL; end the pending read txn first.
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        if int(connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()) != 0:
            raise RuntimeError("SQLite FK enforcement could not be suspended")
    try:
        yield
        connection.commit()
    finally:
        if previous:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        problems = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise RuntimeError("Foreign key integrity check failed after SQLite migration")


def _legacy_fk(table: str, column: str) -> str:
    inspector = sa.inspect(op.get_bind())
    constraints = [
        fk for fk in inspector.get_foreign_keys(table)
        if fk["referred_table"] == "users"
        and fk["constrained_columns"] == [column]
    ]
    if len(constraints) != 1:
        raise RuntimeError(f"Expected one legacy FK on {table}.{column}")
    return constraints[0]["name"] or f"fk_{table}_{column}_users"


def upgrade() -> None:
    with sqlite_batch_rebuild():
        for table, column in (("events", "owner_id"), ("orders", "customer_id")):
            name = _legacy_fk(table, column)
            with op.batch_alter_table(table, naming_convention=NAMES) as batch:
                batch.drop_constraint(name, type_="foreignkey")


def downgrade() -> None:
    with sqlite_batch_rebuild():
        for table, column in (("orders", "customer_id"), ("events", "owner_id")):
            with op.batch_alter_table(table, naming_convention=NAMES) as batch:
                batch.create_foreign_key(
                    f"fk_{table}_{column}_users", "users", [column], ["id"],
                )
