from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SeatStatus = Literal["available", "held", "booked"]


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    venue: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    # The seat grid: rows are labelled A, B, C... and seats numbered from 1
    rows: int = Field(ge=1, le=26)
    seats_per_row: int = Field(ge=1, le=50)
    price_cents: int = Field(ge=0)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    venue: str
    starts_at: datetime
    total_seats: int
    available_seats: int


class SeatOut(BaseModel):
    id: int
    row_label: str
    number: int
    price_cents: int
    status: SeatStatus
    mine: bool  # held or booked by the user asking (always false when logged out)
