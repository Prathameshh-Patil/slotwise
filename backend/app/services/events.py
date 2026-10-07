import string
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, Event, Seat
from app.schemas.event import EventCreate, EventOut, SeatOut


def occupies_seat(now: datetime):
    """SQL condition for a booking that currently takes its seat.

    A hold past its expiry no longer counts, even before the background task
    has marked it expired, so a stalled worker never makes seats look taken.
    """
    return or_(
        Booking.status == BookingStatus.CONFIRMED,
        and_(Booking.status == BookingStatus.HELD, Booking.hold_expires_at > now),
    )


def create_event(db: Session, body: EventCreate) -> Event:
    event = Event(**body.model_dump(exclude={"rows", "seats_per_row", "price_cents"}))
    event.seats = [
        Seat(row_label=row, number=number, price_cents=body.price_cents)
        for row in string.ascii_uppercase[: body.rows]
        for number in range(1, body.seats_per_row + 1)
    ]
    db.add(event)
    db.commit()
    return event


def list_events(db: Session, event_id: int | None = None) -> list[EventOut]:
    """Upcoming events (or one event by id) with live seat counts."""
    now = datetime.now(UTC)
    taken = select(Booking.seat_id).where(occupies_seat(now)).subquery()
    query = (
        select(
            Event,
            func.count(Seat.id).label("total"),
            func.count(Seat.id).filter(taken.c.seat_id.is_(None)).label("available"),
        )
        .join(Seat, Seat.event_id == Event.id)
        .outerjoin(taken, taken.c.seat_id == Seat.id)
        .group_by(Event.id)
        .order_by(Event.starts_at)
    )
    if event_id is None:
        query = query.where(Event.starts_at > now)
    else:
        query = query.where(Event.id == event_id)

    return [
        EventOut(
            id=event.id,
            title=event.title,
            description=event.description,
            venue=event.venue,
            starts_at=event.starts_at,
            total_seats=total,
            available_seats=available,
        )
        for event, total, available in db.execute(query)
    ]


def seat_map(db: Session, event_id: int, viewer_id: int | None) -> list[SeatOut]:
    now = datetime.now(UTC)
    query = (
        select(Seat, Booking.status, Booking.user_id)
        .outerjoin(Booking, and_(Booking.seat_id == Seat.id, occupies_seat(now)))
        .where(Seat.event_id == event_id)
        .order_by(Seat.row_label, Seat.number)
    )
    seats = []
    for seat, booking_status, owner_id in db.execute(query):
        if booking_status is None:
            status = "available"
        elif booking_status == BookingStatus.HELD:
            status = "held"
        else:
            status = "booked"
        seats.append(
            SeatOut(
                id=seat.id,
                row_label=seat.row_label,
                number=seat.number,
                price_cents=seat.price_cents,
                status=status,
                mine=owner_id is not None and owner_id == viewer_id,
            )
        )
    return seats
