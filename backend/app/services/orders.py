"""Holding, confirming and cancelling seats, one order at a time.

How double booking is prevented: the bookings table has a partial unique index
allowing only one 'held' or 'confirmed' booking per seat. hold_seats simply tries
to insert one booking per requested seat. If two requests race for a seat, both
inserts reach Postgres, the second waits for the first to commit and then fails
with a unique violation, which we turn into "seat unavailable". No application-
level check can do this safely, because two requests could both check, both see
the seat free, and both insert.

Multi-seat orders are all or nothing: every seat's insert runs in one
transaction, so if any seat is taken, none are held.
"""

from datetime import UTC, datetime, timedelta

from psycopg.errors import DeadlockDetected, UniqueViolation
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import Booking, BookingStatus, Event, Order, OrderHistory, Seat, User
from app.models.booking import ACTIVE_STATUSES

MAX_SEATS_PER_ORDER = 10


class BookingError(Exception):
    """A booking action that can't be done. `status_code` is the HTTP status to return."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def occupies_seat(now: datetime):
    """SQL condition (on Booking joined to Order) for a booking that takes its seat now.

    A hold past its expiry no longer counts, even before the background task
    has marked it expired, so a stalled worker never makes seats look taken.
    """
    return or_(
        Booking.status == BookingStatus.CONFIRMED,
        and_(Booking.status == BookingStatus.HELD, Order.hold_expires_at > now),
    )


def seat_label(seat: Seat) -> str:
    return f"{seat.row_label}{seat.number}"


def _set_status(
    db: Session,
    order_ids: list[int],
    status: BookingStatus,
    actor_id: int | None,
    detail: str,
    now: datetime,
) -> None:
    """Move orders' bookings to `status` and write one history row per order."""
    db.execute(update(Booking).where(Booking.order_id.in_(order_ids)).values(status=status))
    db.add_all(
        OrderHistory(
            order_id=order_id, status=status, actor_id=actor_id, detail=detail, created_at=now
        )
        for order_id in order_ids
    )


def expire_lapsed_holds(
    db: Session, *, seat_ids: list[int] | None = None, user_id: int | None = None
) -> int:
    """Mark held orders past their expiry as expired. Returns how many were changed."""
    now = datetime.now(UTC)
    query = update(Order).where(Order.status == BookingStatus.HELD, Order.hold_expires_at <= now)
    if seat_ids is not None:
        held_on_seats = select(Booking.order_id).where(
            Booking.seat_id.in_(seat_ids), Booking.status == BookingStatus.HELD
        )
        query = query.where(Order.id.in_(held_on_seats))
    if user_id is not None:
        query = query.where(Order.user_id == user_id)
    expired = list(
        db.scalars(
            query.values(
                status=BookingStatus.EXPIRED, expired_at=now, hold_expires_at=None
            ).returning(Order.id)
        )
    )
    if expired:
        _set_status(db, expired, BookingStatus.EXPIRED, None, "Hold ran out before payment", now)
    return len(expired)


def hold_seats(db: Session, user: User, event_id: int, seat_ids: list[int]) -> Order:
    seat_ids = sorted(set(seat_ids))
    if not seat_ids:
        raise BookingError(422, "Pick at least one seat")
    if len(seat_ids) > MAX_SEATS_PER_ORDER:
        raise BookingError(422, f"You can book at most {MAX_SEATS_PER_ORDER} seats at once")

    event = db.get(Event, event_id)
    if event is None:
        raise BookingError(404, "Event not found")
    now = datetime.now(UTC)
    if event.starts_at <= now:
        raise BookingError(400, "This event has already started")
    seats = list(db.scalars(select(Seat).where(Seat.id.in_(seat_ids), Seat.event_id == event_id)))
    if len(seats) != len(seat_ids):
        raise BookingError(404, "Some of those seats don't exist at this event")

    # A lapsed hold still counts for the unique index until it is marked expired.
    # Do that here, in the same transaction, so seats free up on time even if
    # the background worker is behind.
    expire_lapsed_holds(db, seat_ids=seat_ids)

    order = Order(
        user_id=user.id,
        event_id=event_id,
        status=BookingStatus.HELD,
        total_cents=sum(s.price_cents for s in seats),
        hold_expires_at=now + timedelta(minutes=settings.hold_minutes),
        created_at=now,
    )
    # Insert seats in id order. If two orders overlap (A wants 1+2, B wants 2+1) and
    # each inserted a different seat first, each would wait for the other forever:
    # a deadlock. Always taking seats in the same order means one simply waits.
    order.bookings = [
        Booking(seat_id=s.id, status=BookingStatus.HELD, price_cents=s.price_cents)
        for s in sorted(seats, key=lambda s: s.id)
    ]
    labels = ", ".join(seat_label(s) for s in sorted(seats, key=lambda s: (s.row_label, s.number)))
    order.history = [
        OrderHistory(
            status=BookingStatus.HELD,
            actor_id=user.id,
            detail=f"Held {len(seats)} seat{'s' if len(seats) > 1 else ''}: {labels}",
            created_at=now,
        )
    ]
    db.add(order)
    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        db.rollback()
        if isinstance(exc.orig, UniqueViolation | DeadlockDetected):
            raise BookingError(409, _taken_message(db, seat_ids)) from exc
        raise
    return get_order(db, order.id)


def _taken_message(db: Session, seat_ids: list[int]) -> str:
    """Say which of the requested seats someone else has (looked up after losing)."""
    now = datetime.now(UTC)
    taken = list(
        db.scalars(
            select(Seat)
            .join(Booking, Booking.seat_id == Seat.id)
            .join(Order, Order.id == Booking.order_id)
            .where(Seat.id.in_(seat_ids), occupies_seat(now))
            .order_by(Seat.row_label, Seat.number)
        )
    )
    if not taken:
        return "Sorry, someone else just took one of those seats"
    labels = ", ".join(seat_label(s) for s in taken)
    verb = "was" if len(taken) == 1 else "were"
    return f"Sorry, {labels} {verb} just taken by someone else. Nothing was held."


def get_order(db: Session, order_id: int) -> Order | None:
    return db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.bookings).selectinload(Booking.seat),
            selectinload(Order.history).selectinload(OrderHistory.actor),
            selectinload(Order.event),
            selectinload(Order.user),
        )
        .execution_options(populate_existing=True)  # reload rows an UPDATE just changed
    )


def get_own_order(db: Session, user: User, order_id: int) -> Order:
    order = get_order(db, order_id)
    # 404 rather than 403 for other users' orders: don't confirm they exist
    if order is None or (order.user_id != user.id and not user.is_admin):
        raise BookingError(404, "Order not found")
    return order


def confirm_order(db: Session, user: User, order_id: int) -> Order:
    order = get_own_order(db, user, order_id)
    if order.user_id != user.id:
        raise BookingError(404, "Order not found")
    now = datetime.now(UTC)
    # One conditional UPDATE, not "read, check, write": if the expiry task runs at
    # the same moment, Postgres row locking lets exactly one of them change the row.
    confirmed = db.scalar(
        update(Order)
        .where(
            Order.id == order_id,
            Order.status == BookingStatus.HELD,
            Order.hold_expires_at > now,
        )
        .values(status=BookingStatus.CONFIRMED, confirmed_at=now, hold_expires_at=None)
        .returning(Order.id)
    )
    if confirmed is None:
        db.rollback()
        raise BookingError(409, "This hold has expired or was already confirmed")
    _set_status(db, [order_id], BookingStatus.CONFIRMED, user.id, "Payment received", now)
    db.commit()

    from app.tasks.bookings import send_booking_confirmation

    send_booking_confirmation.delay(order_id)
    return get_order(db, order_id)


def cancel_order(db: Session, user: User, order_id: int) -> Order:
    order = get_own_order(db, user, order_id)
    if order.event.starts_at <= datetime.now(UTC):
        raise BookingError(400, "This event has already started")
    now = datetime.now(UTC)
    was = order.status
    cancelled = db.scalar(
        update(Order)
        .where(Order.id == order_id, Order.status.in_(ACTIVE_STATUSES))
        .values(status=BookingStatus.CANCELLED, cancelled_at=now, hold_expires_at=None)
        .returning(Order.id)
    )
    if cancelled is None:
        db.rollback()
        raise BookingError(409, "This order is no longer active")
    by_admin = order.user_id != user.id
    detail = ("Released the hold" if was == BookingStatus.HELD else "Cancelled the booking") + (
        " (by an admin)" if by_admin else ""
    )
    _set_status(db, [order_id], BookingStatus.CANCELLED, user.id, detail, now)
    db.commit()
    return get_order(db, order_id)


def _orders_query():
    return select(Order).options(
        selectinload(Order.bookings).selectinload(Booking.seat),
        selectinload(Order.history).selectinload(OrderHistory.actor),
        selectinload(Order.event),
        selectinload(Order.user),
    )


def list_user_orders(db: Session, user: User) -> list[Order]:
    expire_lapsed_holds(db, user_id=user.id)
    db.commit()
    return list(
        db.scalars(
            _orders_query().where(Order.user_id == user.id).order_by(Order.created_at.desc())
        )
    )


def list_all_orders(
    db: Session,
    *,
    event_id: int | None = None,
    status: BookingStatus | None = None,
    email: str | None = None,
    limit: int = 200,
) -> list[Order]:
    """Every order, newest first, for the admin history page."""
    expire_lapsed_holds(db)
    db.commit()
    query = _orders_query().order_by(Order.created_at.desc()).limit(limit)
    if event_id is not None:
        query = query.where(Order.event_id == event_id)
    if status is not None:
        query = query.where(Order.status == status)
    if email:
        query = query.join(User, User.id == Order.user_id).where(
            User.email.ilike(f"%{email.strip()}%")
        )
    return list(db.scalars(query))
