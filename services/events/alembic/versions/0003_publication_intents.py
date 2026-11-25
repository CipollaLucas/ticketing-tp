"""Events-local publication intent and metadata revision, no sale commands.

Existing events remain unchanged in status. Revision zero means that Events
has not yet started the new coordinated publication protocol.
"""
import sqlalchemy as sa

from alembic import op

revision = "0003_publication_intents"
down_revision = "0002_event_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column(
            "revision", sa.Integer(), nullable=False, server_default="0",
        ))
    op.create_table(
        "event_publication_intents",
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("command_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("event_revision", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.CheckConstraint("phase = 'prepared'", name="valid_publication_intent_phase"),
        sa.CheckConstraint("event_revision >= 1", name="positive_publication_revision"),
    )


def downgrade() -> None:
    op.drop_table("event_publication_intents")
    with op.batch_alter_table("events") as batch:
        batch.drop_column("revision")
