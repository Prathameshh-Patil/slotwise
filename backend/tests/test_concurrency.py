"""The headline guarantee: many people grabbing the same seats at once, one wins.

Each thread uses its own database connection, and a barrier releases them all
at the same instant, so their inserts really do reach Postgres together.
"""

import threading
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models import Booking, User
from app.services.orders import BookingError, hold_seats

RACERS = 12  # stays under the connection pool size (5 + 10 overflow)


def race(jobs: list[Callable[[], object]]) -> list[object]:
    """Run every job at the same instant on its own thread; return their results."""
    barrier = threading.Barrier(len(jobs))
    results: list[object] = []
    lock = threading.Lock()

    def run(job):
        barrier.wait()
        result = job()
        with lock:
            results.append(result)

    threads = [threading.Thread(target=run, args=(job,)) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def try_hold(user_id: int, event_id: int, seat_ids: list[int]) -> Callable[[], str]:
    def job() -> str:
        with SessionLocal() as db:
            try:
                hold_seats(db, db.get(User, user_id), event_id, seat_ids)
                return "won"
            except BookingError as exc:
                return str(exc.status_code)

    return job


def user_ids(make_user, count: int) -> list[int]:
    for i in range(count):
        make_user(f"racer{i}@example.com")
    with SessionLocal() as db:
        return [u.id for u in db.query(User).all()]


def test_only_one_of_many_simultaneous_holds_succeeds(event, seat_id, make_user):
    ids = user_ids(make_user, RACERS)

    results = race([try_hold(uid, event.id, [seat_id]) for uid in ids])

    assert sorted(results) == ["409"] * (RACERS - 1) + ["won"]
    with SessionLocal() as db:
        assert db.query(Booking).filter_by(seat_id=seat_id).count() == 1


def test_overlapping_multi_seat_orders_never_share_a_seat_or_deadlock(event, make_user):
    """Users ask for overlapping pairs of seats, listed in opposite orders.

    The result must be clean 201s and 409s, never a 500 or a seat in two active
    bookings. (hold_seats also inserts seats in id order so that two overlapping
    orders can't deadlock; this race is too short to trigger a deadlock reliably,
    so the test checks the outcome rather than the sorting itself.)
    """
    ids = user_ids(make_user, RACERS)
    s = [seat.id for seat in event.seats]
    pairs = [[s[0], s[1]], [s[1], s[0]], [s[1], s[2]], [s[2], s[1]]]

    results = race([try_hold(uid, event.id, pairs[i % 4]) for i, uid in enumerate(ids)])

    # Every pair includes seat s[1], so exactly one order can win
    assert sorted(results) == ["409"] * (RACERS - 1) + ["won"]
    with SessionLocal() as db:
        active = db.query(Booking).filter(Booking.status.in_(["held", "confirmed"])).all()
        taken = [b.seat_id for b in active]
        assert len(taken) == len(set(taken))  # no seat in two active bookings


def test_simultaneous_http_requests_get_one_201_and_the_rest_409(event, seat_id, make_user):
    headers = [make_user(f"web{i}@example.com") for i in range(RACERS)]

    def post(h):
        return lambda: (
            TestClient(app)
            .post(f"/events/{event.id}/orders", json={"seat_ids": [seat_id]}, headers=h)
            .status_code
        )

    codes = race([post(h) for h in headers])

    assert sorted(codes) == [201] + [409] * (RACERS - 1)
