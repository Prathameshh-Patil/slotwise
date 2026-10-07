import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, func, text
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


class Booking(Base):
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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id", ondelete="CASCADE"), index=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            values_callable=lambda e: [m.value for m in e],  # store "held", not "HELD"
        ),
        default=BookingStatus.HELD,
    )
    hold_expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    confirmed_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()
    seat: Mapped[Seat] = relationship()

    @property
    def event(self) -> Event:
        return self.seat.event
