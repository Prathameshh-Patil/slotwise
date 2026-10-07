import logging

from app.core.db import SessionLocal
from app.services.orders import expire_lapsed_holds, get_order, seat_label
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def release_expired_holds() -> int:
    """Mark lapsed holds as expired (and log it in their history).

    Seats already read as free once a hold lapses (the queries check the time),
    and hold_seats expires a lapsed hold before inserting. This task keeps the
    stored status and history accurate, e.g. for "My bookings".
    """
    with SessionLocal() as db:
        count = expire_lapsed_holds(db)
        db.commit()
    if count:
        logger.info("Released %d expired hold(s)", count)
    return count


@celery_app.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_booking_confirmation(order_id: int) -> None:
    """Email the user their booking. Sending is stubbed out: it logs the message.

    It runs in the worker so a slow or failing mail server never delays the
    API's response, and failures are retried with growing delays.
    """
    with SessionLocal() as db:
        order = get_order(db, order_id)
        if order is None:
            return
        seats = ", ".join(sorted(seat_label(b.seat) for b in order.bookings))
        logger.info(
            "Email to %s: seats %s for %s on %s are confirmed (order #%d, total %.2f)",
            order.user.email,
            seats,
            order.event.title,
            order.event.starts_at.isoformat(),
            order.id,
            order.total_cents / 100,
        )
