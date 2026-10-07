from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    venue: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    seats: Mapped[list["Seat"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Seat.id"
    )


class Seat(Base):
    """A physical seat at one event. Whether it is free is decided by its bookings."""

    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("event_id", "row_label", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    row_label: Mapped[str] = mapped_column(String(5))
    number: Mapped[int]
    price_cents: Mapped[int]

    event: Mapped[Event] = relationship(back_populates="seats")
