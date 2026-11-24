"""Events-owned metadata only; no user/order/inventory tables."""
import sqlalchemy as sa

from alembic import op

revision = "0001_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(5000), nullable=False),
        sa.Column("venue", sa.String(300), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published')", name="valid_event_status"),
        sa.CheckConstraint("end_at > start_at", name="valid_event_dates"),
    )
    op.create_index("ix_events_owner_id", "events", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_events_owner_id", table_name="events")
    op.drop_table("events")
