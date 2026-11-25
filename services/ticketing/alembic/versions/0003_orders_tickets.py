"""Ticketing-owned orders and tickets. External event/customer UUIDs are NOT foreign keys."""

import sqlalchemy as sa

from alembic import op

revision = "0003_orders_tickets"
down_revision = "0002_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("customer_id", "idempotency_key", name="uq_order_idempotency"),
        sa.CheckConstraint("total_minor >= 0", name="valid_order_total"),
        sa.CheckConstraint("currency IN ('ARS', 'USD', 'EUR')", name="valid_order_currency"),
        sa.CheckConstraint("status = 'confirmed'", name="valid_order_status"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_event_id", "orders", ["event_id"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("zone_id", sa.Uuid(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("order_id", "zone_id", name="uq_item_order_zone"),
        sa.UniqueConstraint("id", "zone_id", name="uq_item_id_zone"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 100", name="valid_item_quantity"),
        sa.CheckConstraint("unit_price_minor >= 0", name="valid_item_price"),
        sa.CheckConstraint(
            "subtotal_minor = quantity * unit_price_minor",
            name="valid_item_subtotal",
        ),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_item_id", sa.Uuid(), nullable=False),
        sa.Column("zone_id", sa.Uuid(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=True, unique=True),
        sa.Column("status", sa.String(5), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_item_id", "zone_id"],
            ["order_items.id", "order_items.zone_id"],
        ),
        sa.ForeignKeyConstraint(
            ["seat_id", "zone_id"],
            ["seats.id", "seats.zone_id"],
        ),
        sa.CheckConstraint("status = 'valid'", name="valid_ticket_status"),
    )
    op.create_index("ix_tickets_order_item_id", "tickets", ["order_item_id"])


def downgrade() -> None:
    op.drop_index("ix_tickets_order_item_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_event_id", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")
