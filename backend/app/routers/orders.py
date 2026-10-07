from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models import BookingStatus, Order
from app.schemas.order import OrderCreate, OrderOut, order_out
from app.services import orders as service
from app.services.orders import BookingError

router = APIRouter(tags=["orders"])


def _run(action: Callable[..., Order], *args) -> OrderOut:
    try:
        return order_out(action(*args))
    except BookingError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from exc


@router.post(
    "/events/{event_id}/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED
)
def hold_seats(event_id: int, body: OrderCreate, db: DbSession, user: CurrentUser) -> OrderOut:
    """Hold one or more seats for a few minutes, all or nothing.

    Returns 409, holding nothing, if anyone else has any of the seats.
    """
    return _run(service.hold_seats, db, user, event_id, body.seat_ids)


@router.get("/orders/me", response_model=list[OrderOut])
def my_orders(db: DbSession, user: CurrentUser) -> list[OrderOut]:
    """Every order I've made, newest first, with seats, prices and full history."""
    return [order_out(o) for o in service.list_user_orders(db, user)]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: DbSession, user: CurrentUser) -> OrderOut:
    return _run(service.get_own_order, db, user, order_id)


@router.post("/orders/{order_id}/confirm", response_model=OrderOut)
def confirm_order(order_id: int, db: DbSession, user: CurrentUser) -> OrderOut:
    """Turn a live hold into a booking. In a real shop, payment would happen here."""
    return _run(service.confirm_order, db, user, order_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, db: DbSession, user: CurrentUser) -> OrderOut:
    """Release a hold or cancel a booking. Admins can cancel anyone's."""
    return _run(service.cancel_order, db, user, order_id)


@router.get("/admin/orders", response_model=list[OrderOut], tags=["admin"])
def all_orders(
    db: DbSession,
    _: AdminUser,
    event_id: int | None = None,
    order_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    email: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[OrderOut]:
    """Booking history for everyone, newest first, filterable by event, status and email."""
    orders = service.list_all_orders(
        db, event_id=event_id, status=order_status, email=email, limit=limit
    )
    return [order_out(o) for o in orders]
