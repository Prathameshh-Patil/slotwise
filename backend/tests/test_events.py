from datetime import UTC, datetime, timedelta

NEW_EVENT = {
    "title": "Comedy Night",
    "venue": "Main Stage",
    "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
    "rows": 3,
    "seats_per_row": 4,
    "price_cents": 1500,
}


def test_admin_can_create_event_with_seat_grid(client, admin_headers):
    response = client.post("/events", json=NEW_EVENT, headers=admin_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["total_seats"] == 12
    assert body["available_seats"] == 12

    seats = client.get(f"/events/{body['id']}/seats").json()
    labels = [f"{s['row_label']}{s['number']}" for s in seats]
    assert labels[:5] == ["A1", "A2", "A3", "A4", "B1"]


def test_regular_user_cannot_create_event(client, user_headers):
    assert client.post("/events", json=NEW_EVENT, headers=user_headers).status_code == 403


def test_logged_out_user_cannot_create_event(client):
    assert client.post("/events", json=NEW_EVENT).status_code == 401


def test_list_shows_only_upcoming_events(client, admin_headers):
    past = {**NEW_EVENT, "title": "Last Year", "starts_at": "2020-01-01T20:00:00Z"}
    client.post("/events", json=past, headers=admin_headers)
    client.post("/events", json=NEW_EVENT, headers=admin_headers)

    titles = [e["title"] for e in client.get("/events").json()]
    assert titles == ["Comedy Night"]


def test_seat_map_shows_held_and_booked_seats(client, event, user_headers, make_user):
    a1, a2 = event.seats[0].id, event.seats[1].id
    other_headers = make_user("other@example.com")
    held = client.post(f"/seats/{a1}/hold", headers=user_headers).json()
    client.post(f"/bookings/{held['id']}/confirm", headers=user_headers)
    client.post(f"/seats/{a2}/hold", headers=other_headers)

    response = client.get(f"/events/{event.id}/seats", headers=user_headers)
    seats = {s["id"]: s for s in response.json()}
    assert seats[a1]["status"] == "booked" and seats[a1]["mine"] is True
    assert seats[a2]["status"] == "held" and seats[a2]["mine"] is False
    assert client.get(f"/events/{event.id}").json()["available_seats"] == 4


def test_unknown_event_is_404(client):
    assert client.get("/events/999").status_code == 404
    assert client.get("/events/999/seats").status_code == 404
