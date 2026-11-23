"""Add event drafts and ownership."""

import sqlalchemy as sa

from alembic import op

revision = "0002_events"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("venue", sa.String(200), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published')", name="valid_event_status"),
        sa.CheckConstraint(
            "end_at IS NULL OR start_at IS NULL OR end_at > start_at",
            name="valid_event_date_range",
        ),
    )
    op.create_index("ix_events_owner_id", "events", ["owner_id"])


def downgrade() -> None:
    op.drop_table("events")
