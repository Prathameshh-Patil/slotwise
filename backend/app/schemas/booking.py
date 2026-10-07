from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import BookingStatus


class BookingSeat(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    row_label: str
    number: int
    price_cents: int


class BookingEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    venue: str
    starts_at: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: BookingStatus
    hold_expires_at: datetime | None
    created_at: datetime
    confirmed_at: datetime | None
    seat: BookingSeat
    event: BookingEvent
