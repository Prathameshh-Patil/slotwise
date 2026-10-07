from collections.abc import Callable

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.models import Booking
from app.schemas.booking import BookingOut
from app.services import bookings as service
from app.services.bookings import BookingError

router = APIRouter(tags=["bookings"])


def _run(action: Callable[..., Booking], *args) -> Booking:
    try:
        return action(*args)
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from exc


@router.post(
    "/seats/{seat_id}/hold", response_model=BookingOut, status_code=status.HTTP_201_CREATED
)
def hold_seat(seat_id: int, db: DbSession, user: CurrentUser) -> Booking:
    """Reserve a seat for a few minutes. Returns 409 if anyone else has it."""
    return _run(service.hold_seat, db, user, seat_id)


@router.post("/bookings/{booking_id}/confirm", response_model=BookingOut)
def confirm_booking(booking_id: int, db: DbSession, user: CurrentUser) -> Booking:
    """Turn a hold into a booking. In a real shop, payment would happen here."""
    return _run(service.confirm_booking, db, user, booking_id)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, db: DbSession, user: CurrentUser) -> Booking:
    return _run(service.cancel_booking, db, user, booking_id)


@router.get("/bookings/me", response_model=list[BookingOut])
def my_bookings(db: DbSession, user: CurrentUser) -> list[Booking]:
    return service.list_user_bookings(db, user)
