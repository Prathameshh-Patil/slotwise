from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import Event, Order
from app.tasks.bookings import release_expired_holds


def hold(client, event, seat_ids, headers):
    return client.post(f"/events/{event.id}/orders", json={"seat_ids": seat_ids}, headers=headers)


def expire_all_holds():
    """Move every hold's expiry into the past, as if the minutes had gone by."""
    with SessionLocal() as db:
        db.execute(update(Order).values(hold_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()


def seat_ids(event, *labels):
    by_label = {f"{s.row_label}{s.number}": s.id for s in event.seats}
    return [by_label[label] for label in labels]


def test_hold_several_seats_then_confirm(client, event, user_headers):
    response = hold(client, event, seat_ids(event, "A1", "A2", "B3"), user_headers)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "held"
    assert [f"{s['row_label']}{s['number']}" for s in order["seats"]] == ["A1", "A2", "B3"]
    assert order["total_cents"] == 3 * 2500
    assert order["hold_expires_at"] is not None

    confirmed = client.post(f"/orders/{order['id']}/confirm", headers=user_headers).json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None
    seats = client.get(f"/events/{event.id}/seats").json()
    assert sum(s["status"] == "booked" for s in seats) == 3


def test_order_is_all_or_nothing(client, event, user_headers, make_user):
    hold(client, event, seat_ids(event, "A2"), make_user("bo@example.com"))

    response = hold(client, event, seat_ids(event, "A1", "A2", "A3"), user_headers)
    assert response.status_code == 409
    assert "A2" in response.json()["detail"]
    # A1 and A3 must not have been held either
    seats = {s["id"]: s for s in client.get(f"/events/{event.id}/seats").json()}
    assert seats[seat_ids(event, "A1")[0]]["status"] == "available"
    assert seats[seat_ids(event, "A3")[0]]["status"] == "available"


def test_order_rules(client, event, user_headers):
    assert hold(client, event, [], user_headers).status_code == 422
    assert hold(client, event, list(range(1, 12)), user_headers).status_code == 422
    assert hold(client, event, [999], user_headers).status_code == 404
    assert client.post("/events/999/orders", json={"seat_ids": [1]}).status_code == 401


def test_seats_from_another_event_are_rejected(client, event, admin_headers, user_headers):
    other = client.post(
        "/events",
        json={
            "title": "Other",
            "venue": "Elsewhere",
            "starts_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "rows": 1,
            "seats_per_row": 1,
            "price_cents": 100,
        },
        headers=admin_headers,
    ).json()
    other_seat = client.get(f"/events/{other['id']}/seats").json()[0]["id"]

    response = hold(client, event, [seat_ids(event, "A1")[0], other_seat], user_headers)
    assert response.status_code == 404


def test_expired_hold_frees_the_seats(client, event, user_headers, make_user):
    first = hold(client, event, seat_ids(event, "A1", "A2"), user_headers).json()
    expire_all_holds()

    second = hold(client, event, seat_ids(event, "A2"), make_user("bo@example.com"))
    assert second.status_code == 201
    late = client.post(f"/orders/{first['id']}/confirm", headers=user_headers)
    assert late.status_code == 409


def test_cannot_confirm_someone_elses_order(client, event, user_headers, make_user):
    order = hold(client, event, seat_ids(event, "A1"), user_headers).json()

    other = make_user("bo@example.com")
    assert client.post(f"/orders/{order['id']}/confirm", headers=other).status_code == 404
    assert client.get(f"/orders/{order['id']}", headers=other).status_code == 404


def test_cancelling_frees_every_seat(client, event, user_headers, make_user):
    order = hold(client, event, seat_ids(event, "A1", "A2"), user_headers).json()
    client.post(f"/orders/{order['id']}/confirm", headers=user_headers)

    cancelled = client.post(f"/orders/{order['id']}/cancel", headers=user_headers).json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None
    again = hold(client, event, seat_ids(event, "A1", "A2"), make_user("bo@example.com"))
    assert again.status_code == 201


def test_cannot_hold_seats_for_a_past_event(client, event, user_headers):
    with SessionLocal() as db:
        db.execute(update(Event).values(starts_at=datetime.now(UTC) - timedelta(hours=1)))
        db.commit()

    assert hold(client, event, seat_ids(event, "A1"), user_headers).status_code == 400


def test_history_records_every_change(client, event, user_headers):
    order = hold(client, event, seat_ids(event, "B1", "A1"), user_headers).json()
    client.post(f"/orders/{order['id']}/confirm", headers=user_headers)
    client.post(f"/orders/{order['id']}/cancel", headers=user_headers)

    history = client.get(f"/orders/{order['id']}", headers=user_headers).json()["history"]
    assert [h["status"] for h in history] == ["held", "confirmed", "cancelled"]
    assert history[0]["detail"] == "Held 2 seats: A1, B1"
    assert all(h["actor_email"] == "user@example.com" for h in history)


def test_expiry_is_recorded_as_done_by_the_system(client, event, user_headers):
    hold(client, event, seat_ids(event, "A1"), user_headers)
    assert release_expired_holds() == 0

    expire_all_holds()
    assert release_expired_holds() == 1
    order = client.get("/orders/me", headers=user_headers).json()[0]
    assert order["status"] == "expired"
    assert order["expired_at"] is not None
    assert order["history"][-1]["status"] == "expired"
    assert order["history"][-1]["actor_email"] is None


def test_price_is_kept_as_it_was_when_booked(client, event, user_headers):
    order = hold(client, event, seat_ids(event, "A1"), user_headers).json()
    with SessionLocal() as db:
        db.execute(update(type(event.seats[0])).values(price_cents=9999))
        db.commit()

    again = client.get(f"/orders/{order['id']}", headers=user_headers).json()
    assert again["seats"][0]["price_cents"] == 2500
    assert again["total_cents"] == 2500


def test_my_orders_lists_only_mine(client, event, user_headers, make_user):
    hold(client, event, seat_ids(event, "A1"), user_headers)
    hold(client, event, seat_ids(event, "A2"), make_user("bo@example.com"))

    mine = client.get("/orders/me", headers=user_headers).json()
    assert [[s["number"] for s in o["seats"]] for o in mine] == [[1]]


def test_admin_sees_and_filters_everyones_history(
    client, event, admin_headers, user_headers, make_user
):
    order = hold(client, event, seat_ids(event, "A1"), user_headers).json()
    client.post(f"/orders/{order['id']}/confirm", headers=user_headers)
    hold(client, event, seat_ids(event, "A2"), make_user("bo@example.com"))

    everything = client.get("/admin/orders", headers=admin_headers).json()
    assert {o["user_email"] for o in everything} == {"user@example.com", "bo@example.com"}
    confirmed = client.get("/admin/orders?status=confirmed", headers=admin_headers).json()
    assert [o["id"] for o in confirmed] == [order["id"]]
    by_email = client.get("/admin/orders?email=bo@", headers=admin_headers).json()
    assert [o["user_email"] for o in by_email] == ["bo@example.com"]

    assert client.get("/admin/orders", headers=user_headers).status_code == 403


def test_admin_can_cancel_any_order(client, event, admin_headers, user_headers):
    order = hold(client, event, seat_ids(event, "A1"), user_headers).json()

    cancelled = client.post(f"/orders/{order['id']}/cancel", headers=admin_headers).json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["history"][-1]["actor_email"] == "admin@example.com"
    assert "(by an admin)" in cancelled["history"][-1]["detail"]
