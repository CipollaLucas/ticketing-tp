"""Add event metadata and publication, preserving identity on downgrade."""

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
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(5000), nullable=False),
        sa.Column("venue", sa.String(300), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published')", name="valid_event_status"),
        sa.CheckConstraint("end_at > start_at", name="valid_event_dates"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 200", name="valid_event_name"),
        sa.CheckConstraint("length(trim(venue)) BETWEEN 1 AND 300", name="valid_event_venue"),
        sa.CheckConstraint("length(description) <= 5000", name="valid_event_description"),
    )
    op.create_index("ix_events_catalog", "events", ["status", "start_at", "id"])
    op.create_index("ix_events_owner", "events", ["owner_id", "start_at", "id"])


def downgrade() -> None:
    op.drop_table("events")
