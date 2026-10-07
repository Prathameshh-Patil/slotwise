from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import Booking, Event
from app.tasks.bookings import release_expired_holds


def expire_all_holds():
    """Move every hold's expiry into the past, as if the minutes had gone by."""
    with SessionLocal() as db:
        db.execute(update(Booking).values(hold_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()


def test_hold_then_confirm(client, seat_id, user_headers):
    hold = client.post(f"/seats/{seat_id}/hold", headers=user_headers)
    assert hold.status_code == 201
    assert hold.json()["status"] == "held"
    assert hold.json()["hold_expires_at"] is not None

    confirm = client.post(f"/bookings/{hold.json()['id']}/confirm", headers=user_headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"
    assert confirm.json()["event"]["title"] == "Jazz Night"


def test_second_user_cannot_hold_a_held_seat(client, seat_id, user_headers, make_user):
    client.post(f"/seats/{seat_id}/hold", headers=user_headers)

    response = client.post(f"/seats/{seat_id}/hold", headers=make_user("bo@example.com"))
    assert response.status_code == 409


def test_holding_requires_login(client, seat_id):
    assert client.post(f"/seats/{seat_id}/hold").status_code == 401


def test_expired_hold_frees_the_seat_for_someone_else(client, seat_id, user_headers, make_user):
    first = client.post(f"/seats/{seat_id}/hold", headers=user_headers).json()
    expire_all_holds()

    second = client.post(f"/seats/{seat_id}/hold", headers=make_user("bo@example.com"))
    assert second.status_code == 201
    # ...and the first user can no longer confirm their lapsed hold
    late = client.post(f"/bookings/{first['id']}/confirm", headers=user_headers)
    assert late.status_code == 409


def test_cannot_confirm_after_hold_expires(client, seat_id, user_headers):
    hold = client.post(f"/seats/{seat_id}/hold", headers=user_headers).json()
    expire_all_holds()

    assert client.post(f"/bookings/{hold['id']}/confirm", headers=user_headers).status_code == 409


def test_cannot_confirm_someone_elses_hold(client, seat_id, user_headers, make_user):
    hold = client.post(f"/seats/{seat_id}/hold", headers=user_headers).json()

    response = client.post(f"/bookings/{hold['id']}/confirm", headers=make_user("bo@example.com"))
    assert response.status_code == 404


def test_cancelling_frees_the_seat(client, seat_id, user_headers, make_user):
    hold = client.post(f"/seats/{seat_id}/hold", headers=user_headers).json()
    client.post(f"/bookings/{hold['id']}/confirm", headers=user_headers)

    cancel = client.post(f"/bookings/{hold['id']}/cancel", headers=user_headers)
    assert cancel.json()["status"] == "cancelled"
    again = client.post(f"/seats/{seat_id}/hold", headers=make_user("bo@example.com"))
    assert again.status_code == 201


def test_cannot_hold_a_seat_for_a_past_event(client, event, seat_id, user_headers):
    with SessionLocal() as db:
        db.execute(update(Event).values(starts_at=datetime.now(UTC) - timedelta(hours=1)))
        db.commit()

    assert client.post(f"/seats/{seat_id}/hold", headers=user_headers).status_code == 400


def test_my_bookings_lists_only_my_bookings(client, event, user_headers, make_user):
    client.post(f"/seats/{event.seats[0].id}/hold", headers=user_headers)
    client.post(f"/seats/{event.seats[1].id}/hold", headers=make_user("bo@example.com"))

    mine = client.get("/bookings/me", headers=user_headers).json()
    assert [(b["seat"]["row_label"], b["seat"]["number"]) for b in mine] == [("A", 1)]


def test_release_task_marks_lapsed_holds_expired(client, seat_id, user_headers):
    client.post(f"/seats/{seat_id}/hold", headers=user_headers)
    assert release_expired_holds() == 0

    expire_all_holds()
    assert release_expired_holds() == 1
    assert client.get("/bookings/me", headers=user_headers).json()[0]["status"] == "expired"
