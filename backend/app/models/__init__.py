# Import every model here so Alembic's autogenerate and Base.metadata see them all.
from app.models.booking import Booking, BookingStatus
from app.models.event import Event, Seat
from app.models.user import User

__all__ = ["Booking", "BookingStatus", "Event", "Seat", "User"]
