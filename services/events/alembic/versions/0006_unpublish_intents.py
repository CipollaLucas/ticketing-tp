"""Events-owned durable unpublish command; no external SQL foreign keys."""
import sqlalchemy as sa

from alembic import op

revision = "0006_unpublish_intents"
down_revision = "0005_metadata_published_phase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_unpublish_intents",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("command_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("event_revision", sa.Integer(), nullable=False),
        sa.Column("expected_gate_version", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.CheckConstraint("phase IN ('prepared','completed')", name="valid_unpublish_phase"),
        sa.CheckConstraint("event_revision >= 1", name="positive_unpublish_revision"),
        sa.CheckConstraint("expected_gate_version >= 0", name="positive_unpublish_gate_version"),
    )


def downgrade() -> None:
    # Do not downgrade an in-flight commercial workflow.
    op.drop_table("event_unpublish_intents")
