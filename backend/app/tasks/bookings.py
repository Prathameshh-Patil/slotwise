import logging

from app.core.db import SessionLocal
from app.models import Booking
from app.services.bookings import expire_lapsed_holds
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def release_expired_holds() -> int:
    """Mark lapsed holds as expired so the seats show as free everywhere.

    Seats already read as free once a hold lapses (the queries check the time),
    and hold_seat expires a lapsed hold before inserting. This task keeps the
    stored status accurate, e.g. for "My bookings".
    """
    with SessionLocal() as db:
        count = expire_lapsed_holds(db)
        db.commit()
    if count:
        logger.info("Released %d expired hold(s)", count)
    return count


@celery_app.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_booking_confirmation(booking_id: int) -> None:
    """Email the user their booking. Sending is stubbed out: it logs the message.

    It runs in the worker so a slow or failing mail server never delays the
    API's response, and failures are retried with growing delays.
    """
    with SessionLocal() as db:
        booking = db.get(Booking, booking_id)
        if booking is None:
            return
        seat, event = booking.seat, booking.event
        logger.info(
            "Email to %s: your seat %s%d for %s on %s is confirmed (booking #%d)",
            booking.user.email,
            seat.row_label,
            seat.number,
            event.title,
            event.starts_at.isoformat(),
            booking.id,
        )
