import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.event import Event, Seat
from app.models.user import User


class BookingStatus(enum.StrEnum):
    HELD = "held"  # reserved for a few minutes while the user confirms
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"  # the hold ran out before it was confirmed


# Statuses that occupy the seat. At most one booking per seat may be in one of these.
ACTIVE_STATUSES = (BookingStatus.HELD, BookingStatus.CONFIRMED)


def status_column() -> Mapped[BookingStatus]:
    # One Postgres enum type, "booking_status", shared by orders, bookings and history
    return mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            values_callable=lambda e: [m.value for m in e],  # store "held", not "HELD"
        ),
        default=BookingStatus.HELD,
    )


class Order(Base):
    """One checkout: a user holding (then confirming) one or more seats at one event.

    The seats in an order move together: they are held, confirmed, cancelled or
    expired as a group, in a single transaction.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    status: Mapped[BookingStatus] = status_column()
    total_cents: Mapped[int]
    hold_expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    confirmed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    expired_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()
    event: Mapped[Event] = relationship()
    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="Booking.seat_id"
    )
    history: Mapped[list["OrderHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderHistory.id"
    )


class Booking(Base):
    """One seat inside an order."""

    __tablename__ = "bookings"
    __table_args__ = (
        # The double-booking guarantee lives here, in the database. A partial unique
        # index only covers rows matching the WHERE clause, so a seat can have any
        # number of cancelled or expired bookings but only one held or confirmed one.
        # If two transactions insert at the same moment, Postgres makes the second
        # wait for the first and then rejects it with a unique violation.
        Index(
            "uq_bookings_one_active_per_seat",
            "seat_id",
            unique=True,
            postgresql_where=text("status IN ('held', 'confirmed')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id", ondelete="CASCADE"), index=True)
    status: Mapped[BookingStatus] = status_column()
    # The price when it was booked: a later price change mustn't rewrite history
    price_cents: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="bookings")
    seat: Mapped[Seat] = relationship()


class OrderHistory(Base):
    """Append-only log: one row every time an order changes status.

    Rows are only ever inserted, never updated, so this is the full story of
    every order: who held which seats, when it was confirmed, cancelled or
    expired, and whether a person or the system did it.
    """

    __tablename__ = "order_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[BookingStatus] = status_column()
    # Who did it: a user id, or NULL when the system did (e.g. a hold expiring)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="history")
    actor: Mapped[User | None] = relationship()
