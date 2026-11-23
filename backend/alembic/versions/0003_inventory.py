"""Inventory constraints and stable zone/seat identifiers."""
import sqlalchemy as sa

from alembic import op

revision = "0003_inventory"
down_revision = "0002_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("capacity", sa.Integer()),
        sa.Column("available", sa.Integer()),
        sa.UniqueConstraint("event_id", "name", name="uq_zone_event_name"),
        sa.UniqueConstraint("id", "mode", name="uq_zone_id_mode"),
        sa.CheckConstraint("mode IN ('general', 'numbered')", name="valid_zone_mode"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 100", name="valid_zone_name"),
        sa.CheckConstraint("price_minor BETWEEN 0 AND 2147483647", name="valid_zone_price"),
        sa.CheckConstraint("currency IN ('ARS', 'USD', 'EUR')", name="valid_zone_currency"),
        sa.CheckConstraint(
            "(mode = 'general' AND capacity IS NOT NULL AND available IS NOT NULL "
            "AND capacity BETWEEN 1 AND 1000000 AND available BETWEEN 0 AND capacity) OR "
            "(mode = 'numbered' AND capacity IS NULL AND available IS NULL)",
            name="valid_zone_capacity",
        ),
    )
    op.create_index("ix_zones_event_id", "zones", ["event_id"])
    op.create_table(
        "seats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("label", sa.String(50), nullable=False),
        sa.UniqueConstraint("zone_id", "label", name="uq_seat_zone_label"),
        sa.UniqueConstraint("id", "zone_id", name="uq_seat_id_zone"),
        sa.ForeignKeyConstraint(["zone_id", "mode"], ["zones.id", "zones.mode"]),
        sa.CheckConstraint("mode = 'numbered'", name="valid_seat_mode"),
        sa.CheckConstraint("length(trim(label)) BETWEEN 1 AND 50", name="valid_seat_label"),
    )
    op.create_index("ix_seats_zone_id", "seats", ["zone_id"])


def downgrade() -> None:
    op.drop_table("seats")
    op.drop_table("zones")
