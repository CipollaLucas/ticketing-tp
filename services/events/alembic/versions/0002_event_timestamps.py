"""Add Stage I event audit timestamps without deleting pre-existing Events rows.

Existing H3 rows had no historic creation timestamps. Their timestamps are
initialized at migration time; this is not a reconstruction of original dates.
"""
import sqlalchemy as sa

from alembic import op

revision = "0002_event_timestamps"
down_revision = "0001_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ))
        batch.add_column(sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ))


def downgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
