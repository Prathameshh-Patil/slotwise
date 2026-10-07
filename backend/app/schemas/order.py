from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import BookingStatus


class OrderCreate(BaseModel):
    seat_ids: list[int] = Field(min_length=1, max_length=10)


class OrderSeat(BaseModel):
    id: int
    row_label: str
    number: int
    price_cents: int  # what this order paid, which may differ from today's price


class OrderEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    venue: str
    starts_at: datetime


class HistoryEntry(BaseModel):
    status: BookingStatus
    detail: str
    actor_email: str | None  # None means the system did it, e.g. a hold expiring
    created_at: datetime


class OrderOut(BaseModel):
    id: int
    status: BookingStatus
    event: OrderEvent
    seats: list[OrderSeat]
    total_cents: int
    hold_expires_at: datetime | None
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    expired_at: datetime | None
    history: list[HistoryEntry]
    user_email: str


def order_out(order) -> OrderOut:
    """Flatten an Order row and its relations into the API shape."""
    seats = sorted(order.bookings, key=lambda b: (b.seat.row_label, b.seat.number))
    return OrderOut(
        id=order.id,
        status=order.status,
        event=OrderEvent.model_validate(order.event),
        seats=[
            OrderSeat(
                id=b.seat.id,
                row_label=b.seat.row_label,
                number=b.seat.number,
                price_cents=b.price_cents,
            )
            for b in seats
        ],
        total_cents=order.total_cents,
        hold_expires_at=order.hold_expires_at,
        created_at=order.created_at,
        confirmed_at=order.confirmed_at,
        cancelled_at=order.cancelled_at,
        expired_at=order.expired_at,
        history=[
            HistoryEntry(
                status=h.status,
                detail=h.detail,
                actor_email=h.actor.email if h.actor else None,
                created_at=h.created_at,
            )
            for h in order.history
        ],
        user_email=order.user.email,
    )
