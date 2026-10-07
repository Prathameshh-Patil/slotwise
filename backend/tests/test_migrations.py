"""The orders migration must carry existing bookings over, not just create tables."""

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.core.db import engine

BEFORE_ORDERS = "2d6b0c496edc"


def test_old_bookings_become_orders_with_history():
    config = Config("alembic.ini")
    command.downgrade(config, BEFORE_ORDERS)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO users (id, email, hashed_password, is_admin)
                    VALUES (1, 'old@example.com', 'x', false);
                INSERT INTO events (id, title, description, venue, starts_at)
                    VALUES (1, 'Old Show', '', 'Hall', now() + interval '1 day');
                INSERT INTO seats (id, event_id, row_label, number, price_cents)
                    VALUES (1, 1, 'A', 1, 700), (2, 1, 'A', 2, 700);
                INSERT INTO bookings (id, user_id, seat_id, status, confirmed_at)
                    VALUES (5, 1, 1, 'confirmed', now()), (6, 1, 2, 'cancelled', NULL);
                """)
            )
        command.upgrade(config, "head")

        with engine.connect() as conn:
            orders = conn.execute(
                text("SELECT id, user_id, event_id, status, total_cents FROM orders ORDER BY id")
            ).all()
            history = conn.execute(
                text("SELECT order_id, status FROM order_history ORDER BY order_id, id")
            ).all()
            next_id = conn.scalar(text("SELECT nextval('orders_id_seq')"))
        assert [tuple(o) for o in orders] == [
            (5, 1, 1, "confirmed", 700),
            (6, 1, 1, "cancelled", 700),
        ]
        assert [tuple(h) for h in history] == [
            (5, "held"),
            (5, "confirmed"),
            (6, "held"),
            (6, "cancelled"),
        ]
        assert next_id > 6  # new orders won't collide with the copied ids
    finally:
        command.upgrade(config, "head")
