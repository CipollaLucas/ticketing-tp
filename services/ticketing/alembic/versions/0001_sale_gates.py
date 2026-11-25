"""H4 sale authority data only; no orders or external service tables."""

import sqlalchemy as sa

from alembic import op

revision = "0001_sale_gates"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sale_gates",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("state", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("event_revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("state IN ('closed','open')", name="valid_sale_gate_state"),
        sa.CheckConstraint("version >= 0", name="nonnegative_sale_gate_version"),
        sa.CheckConstraint("event_revision >= 0", name="nonnegative_metadata_revision"),
    )
    op.create_table(
        "sale_gate_commands",
        sa.Column("command_id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("sale_gates.event_id"), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("event_revision", sa.Integer(), nullable=False),
        sa.Column("result_state", sa.String(8), nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sale_gate_commands")
    op.drop_table("sale_gates")
