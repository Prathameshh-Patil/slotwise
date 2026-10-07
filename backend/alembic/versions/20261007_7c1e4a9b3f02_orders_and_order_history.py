"""orders and order history

Group bookings into orders so several seats can be held and confirmed together,
and record every status change in order_history.

Existing bookings each become a one-seat order (with the same id), and get a
history row for when they were held plus one for their current status.

Revision ID: 7c1e4a9b3f02
Revises: 2d6b0c496edc
Create Date: 2026-10-07 11:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7c1e4a9b3f02"
down_revision: str | None = "2d6b0c496edc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The enum type already exists (created by the first migration); don't create it again
status_enum = postgresql.ENUM(
    "held", "confirmed", "cancelled", "expired", name="booking_status", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_created_at"), "orders", ["created_at"], unique=False)
    op.create_index(op.f("ix_orders_event_id"), "orders", ["event_id"], unique=False)
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"], unique=False)

    op.create_table(
        "order_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_history_order_id"), "order_history", ["order_id"], unique=False)

    # New booking columns start nullable, get filled from existing data, then tighten
    op.add_column("bookings", sa.Column("order_id", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("price_cents", sa.Integer(), nullable=True))

    # Data migration: one order per existing booking, reusing the booking's id
    op.execute(
        """
        INSERT INTO orders (id, user_id, event_id, status, total_cents, hold_expires_at,
                            created_at, confirmed_at, cancelled_at, expired_at)
        SELECT b.id, b.user_id, s.event_id, b.status, s.price_cents,
               CASE WHEN b.status = 'held' THEN b.hold_expires_at END,
               b.created_at, b.confirmed_at,
               CASE WHEN b.status = 'cancelled' THEN b.created_at END,
               CASE WHEN b.status = 'expired' THEN b.hold_expires_at END
        FROM bookings b JOIN seats s ON s.id = b.seat_id
        """
    )
    op.execute(
        """
        UPDATE bookings b SET order_id = b.id, price_cents = s.price_cents
        FROM seats s WHERE s.id = b.seat_id
        """
    )
    # The ids were set by hand, so move the id counter past them
    op.execute(
        "SELECT setval('orders_id_seq', COALESCE((SELECT MAX(id) FROM orders), 0) + 1, false)"
    )
    op.execute(
        """
        INSERT INTO order_history (order_id, status, actor_id, detail, created_at)
        SELECT id, 'held', user_id, 'Held 1 seat', created_at FROM orders
        UNION ALL
        SELECT id, status, NULL, 'Recorded before history tracking began',
               COALESCE(confirmed_at, expired_at, created_at)
        FROM orders WHERE status <> 'held'
        """
    )

    op.alter_column("bookings", "order_id", nullable=False)
    op.alter_column("bookings", "price_cents", nullable=False)
    op.create_foreign_key(
        "bookings_order_id_fkey", "bookings", "orders", ["order_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(op.f("ix_bookings_order_id"), "bookings", ["order_id"], unique=False)

    # These now live on the order
    op.drop_index(op.f("ix_bookings_user_id"), table_name="bookings")
    op.drop_column("bookings", "user_id")
    op.drop_column("bookings", "hold_expires_at")
    op.drop_column("bookings", "confirmed_at")


def downgrade() -> None:
    op.add_column("bookings", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column(
        "bookings", sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("bookings", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE bookings b
        SET user_id = o.user_id, hold_expires_at = o.hold_expires_at,
            confirmed_at = o.confirmed_at
        FROM orders o WHERE o.id = b.order_id
        """
    )
    op.alter_column("bookings", "user_id", nullable=False)
    op.create_foreign_key(
        "bookings_user_id_fkey", "bookings", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(op.f("ix_bookings_user_id"), "bookings", ["user_id"], unique=False)

    op.drop_index(op.f("ix_bookings_order_id"), table_name="bookings")
    op.drop_constraint("bookings_order_id_fkey", "bookings", type_="foreignkey")
    op.drop_column("bookings", "price_cents")
    op.drop_column("bookings", "order_id")

    op.drop_index(op.f("ix_order_history_order_id"), table_name="order_history")
    op.drop_table("order_history")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_event_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_created_at"), table_name="orders")
    op.drop_table("orders")
