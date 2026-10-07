"""Holding, confirming and cancelling seats.

How double booking is prevented: the bookings table has a partial unique index
allowing only one 'held' or 'confirmed' booking per seat. hold_seat simply tries
to insert one. If two requests race for the same seat, both inserts reach
Postgres, the second waits for the first to commit and then fails with a unique
violation, which we turn into "seat unavailable". No application-level check
can do this safely, because two requests could both check, both see the seat
free, and both insert.
"""

from datetime import UTC, datetime, timedelta

from psycopg.errors import UniqueViolation
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Booking, BookingStatus, Seat, User
from app.models.booking import ACTIVE_STATUSES


class BookingError(Exception):
    """A booking action that can't be done. `status_code` is the HTTP status to return."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def expire_lapsed_holds(
    db: Session, *, seat_id: int | None = None, user_id: int | None = None
) -> int:
    """Mark holds past their expiry as expired. Returns how many were changed."""
    query = update(Booking).where(
        Booking.status == BookingStatus.HELD,
        Booking.hold_expires_at <= datetime.now(UTC),
    )
    if seat_id is not None:
        query = query.where(Booking.seat_id == seat_id)
    if user_id is not None:
        query = query.where(Booking.user_id == user_id)
    return db.execute(query.values(status=BookingStatus.EXPIRED)).rowcount


def hold_seat(db: Session, user: User, seat_id: int) -> Booking:
    seat = db.get(Seat, seat_id)
    if seat is None:
        raise BookingError(404, "Seat not found")
    now = datetime.now(UTC)
    if seat.event.starts_at <= now:
        raise BookingError(400, "This event has already started")

    # A lapsed hold still counts for the unique index until it is marked expired.
    # Do that here, in the same transaction, so the seat frees up on time even
    # if the background worker is behind.
    expire_lapsed_holds(db, seat_id=seat_id)
    booking = Booking(
        user_id=user.id,
        seat_id=seat_id,
        status=BookingStatus.HELD,
        hold_expires_at=now + timedelta(minutes=settings.hold_minutes),
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if isinstance(exc.orig, UniqueViolation):
            raise BookingError(409, "Sorry, someone else just took this seat") from exc
        raise
    return booking


def _get_own_booking(db: Session, user: User, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    # 404 rather than 403 for other users' bookings: don't confirm they exist
    if booking is None or booking.user_id != user.id:
        raise BookingError(404, "Booking not found")
    return booking


def confirm_booking(db: Session, user: User, booking_id: int) -> Booking:
    _get_own_booking(db, user, booking_id)
    now = datetime.now(UTC)
    # One conditional UPDATE, not "read, check, write": if the expiry task runs at
    # the same moment, Postgres row locking lets exactly one of them change the row.
    confirmed = db.scalar(
        update(Booking)
        .where(
            Booking.id == booking_id,
            Booking.status == BookingStatus.HELD,
            Booking.hold_expires_at > now,
        )
        .values(status=BookingStatus.CONFIRMED, confirmed_at=now, hold_expires_at=None)
        .returning(Booking.id)
    )
    if confirmed is None:
        db.rollback()
        raise BookingError(409, "This hold has expired or was already confirmed")
    db.commit()

    from app.tasks.bookings import send_booking_confirmation

    send_booking_confirmation.delay(booking_id)
    return _refresh(db, booking_id)


def cancel_booking(db: Session, user: User, booking_id: int) -> Booking:
    booking = _get_own_booking(db, user, booking_id)
    if booking.seat.event.starts_at <= datetime.now(UTC):
        raise BookingError(400, "This event has already started")
    cancelled = db.scalar(
        update(Booking)
        .where(Booking.id == booking_id, Booking.status.in_(ACTIVE_STATUSES))
        .values(status=BookingStatus.CANCELLED, hold_expires_at=None)
        .returning(Booking.id)
    )
    if cancelled is None:
        db.rollback()
        raise BookingError(409, "This booking is no longer active")
    db.commit()
    return _refresh(db, booking_id)


def list_user_bookings(db: Session, user: User) -> list[Booking]:
    expire_lapsed_holds(db, user_id=user.id)
    db.commit()
    return list(
        db.scalars(
            select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())
        )
    )


def _refresh(db: Session, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    db.refresh(booking)  # the UPDATE ran in SQL; reload the row the session cached
    return booking
