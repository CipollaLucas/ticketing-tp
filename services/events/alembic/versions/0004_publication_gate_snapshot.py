"""Persist a confirmed closed Ticketing gate CAS version, safely nullable.

No opening or publication can be triggered by this migration.
"""
import sqlalchemy as sa

from alembic import op

revision = "0004_publication_gate_snapshot"
down_revision = "0003_publication_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("event_publication_intents") as batch:
        batch.add_column(sa.Column("expected_gate_version", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "nonnegative_expected_gate_version",
            "expected_gate_version IS NULL OR expected_gate_version >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("event_publication_intents") as batch:
        batch.drop_constraint("nonnegative_expected_gate_version", type_="check")
        batch.drop_column("expected_gate_version")
