"""Permit metadata-published phase for durable publication command replay."""
from alembic import op

revision = "0005_metadata_published_phase"
down_revision = "0004_publication_gate_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("event_publication_intents") as batch:
        batch.drop_constraint("valid_publication_intent_phase", type_="check")
        batch.create_check_constraint(
            "valid_publication_intent_phase",
            "phase IN ('prepared','metadata_published')",
        )


def downgrade() -> None:
    # Only safe if no publication was committed; otherwise rollback must be
    # coordinated, never silently discard an in-flight publication.
    with op.batch_alter_table("event_publication_intents") as batch:
        batch.drop_constraint("valid_publication_intent_phase", type_="check")
        batch.create_check_constraint(
            "valid_publication_intent_phase",
            "phase = 'prepared'",
        )
