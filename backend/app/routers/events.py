from fastapi import APIRouter, HTTPException, status

from app.core.deps import AdminUser, DbSession, OptionalUser
from app.schemas.event import EventCreate, EventOut, SeatOut
from app.services import events as service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def list_events(db: DbSession) -> list[EventOut]:
    """Upcoming events, soonest first."""
    return service.list_events(db)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, db: DbSession, _: AdminUser) -> EventOut:
    event = service.create_event(db, body)
    return service.list_events(db, event.id)[0]


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: DbSession) -> EventOut:
    found = service.list_events(db, event_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event not found")
    return found[0]


@router.get("/{event_id}/seats", response_model=list[SeatOut])
def get_seats(event_id: int, db: DbSession, user: OptionalUser) -> list[SeatOut]:
    seats = service.seat_map(db, event_id, user.id if user else None)
    if not seats:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event not found")
    return seats
