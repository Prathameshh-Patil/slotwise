"""The headline guarantee: many people grabbing one seat at once, exactly one wins.

Each thread uses its own database connection, and a barrier releases them all
at the same instant, so their inserts really do reach Postgres together.
"""

import threading

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models import Booking, User
from app.services.bookings import BookingError, hold_seat

RACERS = 12  # stays under the connection pool size (5 + 10 overflow)


def test_only_one_of_many_simultaneous_holds_succeeds(seat_id, make_user):
    for i in range(RACERS):
        make_user(f"racer{i}@example.com")
    with SessionLocal() as db:
        user_ids = [u.id for u in db.query(User).all()]

    barrier = threading.Barrier(RACERS)
    results: list[str] = []
    lock = threading.Lock()

    def race(user_id: int) -> None:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait()
            try:
                hold_seat(db, user, seat_id)
                outcome = "won"
            except BookingError as exc:
                outcome = str(exc.status_code)
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=race, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["409"] * (RACERS - 1) + ["won"]
    with SessionLocal() as db:
        assert db.query(Booking).filter_by(seat_id=seat_id).count() == 1


def test_simultaneous_http_requests_get_one_201_and_the_rest_409(seat_id, make_user):
    headers = [make_user(f"web{i}@example.com") for i in range(RACERS)]
    barrier = threading.Barrier(RACERS)
    codes: list[int] = []
    lock = threading.Lock()

    def race(h: dict[str, str]) -> None:
        client = TestClient(app)
        barrier.wait()
        code = client.post(f"/seats/{seat_id}/hold", headers=h).status_code
        with lock:
            codes.append(code)

    threads = [threading.Thread(target=race, args=(h,)) for h in headers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(codes) == [201] + [409] * (RACERS - 1)
