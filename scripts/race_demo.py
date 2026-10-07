"""Watch the double-booking guarantee hold up against the running API.

Registers N users, then has all of them try to hold the same seat at the same
instant. Exactly one should get 201; everyone else should get 409.

    python3 scripts/race_demo.py                 # 50 users, a random free seat
    python3 scripts/race_demo.py --users 200 --api http://localhost:8000
    python3 scripts/race_demo.py --api http://localhost:8080/api   # the local deployment

Only uses the standard library, so it runs with any Python 3.10+.
"""

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter


def call(api, method, path, *, token=None, json_body=None, form=None):
    headers, data = {}, None
    if json_body is not None:
        data, headers["Content-Type"] = json.dumps(json_body).encode(), "application/json"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(api + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or "null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or "null")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=50)
    args = parser.parse_args()

    status, events = call(args.api, "GET", "/events")
    if status != 200 or not events:
        raise SystemExit("No events found. Seed some with: docker compose exec api python -m app.seed")
    event = events[0]
    _, seats = call(args.api, "GET", f"/events/{event['id']}/seats")
    free = [s for s in seats if s["status"] == "available"]
    if not free:
        raise SystemExit(f"No free seats left at {event['title']}")
    seat = random.choice(free)

    print(f"Registering {args.users} users...")
    run = int(time.time())
    tokens = []
    for i in range(args.users):
        email, password = f"racer{run}-{i}@example.com", "password123"
        call(args.api, "POST", "/auth/register", json_body={"email": email, "password": password})
        _, body = call(args.api, "POST", "/auth/login", form={"username": email, "password": password})
        tokens.append(body["access_token"])

    label = f"{seat['row_label']}{seat['number']}"
    print(f"{args.users} users grabbing seat {label} at {event['title']} at the same moment...")
    barrier = threading.Barrier(args.users)
    codes = Counter()
    lock = threading.Lock()

    def grab(token):
        barrier.wait()
        code, _ = call(
            args.api,
            "POST",
            f"/events/{event['id']}/orders",
            token=token,
            json_body={"seat_ids": [seat["id"]]},
        )
        with lock:
            codes[code] += 1

    threads = [threading.Thread(target=grab, args=(t,)) for t in tokens]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"  201 Created (got the seat): {codes[201]}")
    print(f"  409 Conflict (seat taken):  {codes[409]}")
    others = {c: n for c, n in codes.items() if c not in (201, 409)}
    if others:
        print(f"  other responses:            {others}")
    print("PASS: exactly one winner" if codes[201] == 1 else "FAIL: expected exactly one winner")


if __name__ == "__main__":
    main()
