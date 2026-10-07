# Slotwise

An event booking platform where users pick a seat and book it, and two people clicking the same seat at the same moment can never both get it.

Built with Next.js, FastAPI, PostgreSQL, Celery and Redis.

## How double booking is prevented

Picking seats creates an **order** holding them: one `bookings` row per seat with status `held`, which expires after 10 minutes unless the order is confirmed. The bookings table has a partial unique index:

```sql
CREATE UNIQUE INDEX uq_bookings_one_active_per_seat
  ON bookings (seat_id) WHERE status IN ('held', 'confirmed');
```

So the database itself allows at most one active booking per seat. When two requests try to hold the same seat at once, both inserts reach Postgres. The second waits for the first to commit and then fails with a unique violation, and the API answers `409 Conflict`. Nothing in the application code has to "check, then insert", which is exactly the pattern that breaks under concurrency.

An order of several seats is **all or nothing**: every seat is inserted in one transaction, so if any one is taken the whole order is rolled back and nothing is held. Seats are inserted in a fixed (id) order, so two overlapping orders can't deadlock waiting for each other.

## Booking history

Every status change is written to `order_history`: who held which seats, when the order was confirmed, cancelled, or expired, and whether a person or the system (an expiring hold) did it. Rows are only ever added, never edited. Each booking also keeps the price it was sold at, so later price changes don't rewrite old orders. Users see their own history under **My bookings**; admins see everyone's under **All bookings**, with filters and totals.

`backend/tests/test_concurrency.py` releases a dozen threads at the same instant against one seat and asserts that exactly one wins. With the index dropped, the same test fails. `scripts/race_demo.py` does the same against the running API with as many users as you like.

## Architecture

```
 browser ──► Next.js (web, :3100) ──► FastAPI (api, :8000) ──► PostgreSQL
                                          │
                                          └─► Redis ──► Celery worker
                                                 ▲         (emails, expiring holds)
                                          Celery beat (every 30 s)
```

| Folder | What it holds |
| --- | --- |
| `backend/app/models` | SQLAlchemy tables: users, events, seats, bookings |
| `backend/app/services` | Business logic: booking rules live in `services/orders.py` |
| `backend/app/routers` | HTTP endpoints, thin wrappers around the services |
| `backend/app/tasks` | Celery app and background tasks |
| `backend/alembic` | Database migrations |
| `frontend/app` | Next.js pages: events, seat map, login, bookings, admin |
| `scripts/race_demo.py` | Fires N simultaneous holds at one seat against the live API |
| `scripts/deploy_local.sh` | Deploys the production stack on this machine |
| `deploy/Caddyfile` | Reverse proxy: one address, `/api` to FastAPI, the rest to Next.js |

## Run it locally

You need Docker.

```
cp .env.example .env                              # first time only
docker compose up --build                         # db, redis, api, worker, beat, web
docker compose exec api python -m app.seed        # demo users and events
```

- App: http://localhost:3100. Log in as `demo@slotwise.dev` / `demo12345`, or `admin@slotwise.dev` / `admin12345` to create events.
- API docs: http://localhost:8000/docs
- Race demo: `python3 scripts/race_demo.py --users 100`

Checks:

```
docker compose exec api pytest -v           # uses a separate slotwise_test database
docker compose exec api ruff check .
cd frontend && npm run lint && npm run build
```

## API

| Method | Path | Who | What |
| --- | --- | --- | --- |
| POST | `/auth/register` | anyone | Create an account |
| POST | `/auth/login` | anyone | Get a JWT (OAuth2 password form) |
| GET | `/auth/me` | user | The logged-in user |
| GET | `/events` | anyone | Upcoming events with seats left |
| POST | `/events` | admin | Create an event and its seat grid |
| GET | `/events/{id}` | anyone | One event |
| GET | `/events/{id}/seats` | anyone | Seat map: available, held or booked |
| POST | `/events/{id}/orders` | user | Hold up to 10 seats, all or nothing (201, or 409 if any is taken) |
| POST | `/orders/{id}/confirm` | owner | Turn a live hold into a booking |
| POST | `/orders/{id}/cancel` | owner, admin | Release a hold or cancel a booking |
| GET | `/orders/me` | user | My orders, with seats, prices and full history |
| GET | `/orders/{id}` | owner, admin | One order |
| GET | `/admin/orders` | admin | Everyone's orders; filter with `event_id`, `status`, `email` |

## Deploy locally (production mode)

```
./scripts/deploy_local.sh
```

This builds the production images and starts the whole stack as its own Compose project (`slotwise-prod`, next to the dev stack), behind a Caddy reverse proxy on **http://localhost:8080**:

- http://localhost:8080 for the app, and http://localhost:8080/api/docs for the API docs
- `.env.prod` is created on first run with random secrets (git-ignored, readable only by you)
- Only port 8080 is open; Postgres, Redis and the API are reachable only inside Docker
- Migrations run on start; demo users and events are seeded

```
./scripts/deploy_local.sh status        # containers and health
./scripts/deploy_local.sh logs worker   # e.g. watch confirmation emails
./scripts/deploy_local.sh backup        # pg_dump into backups/
./scripts/deploy_local.sh down          # stop (keeps data)
./scripts/deploy_local.sh destroy       # stop and delete the database
python3 scripts/race_demo.py --api http://localhost:8080/api
```

To deploy on a real server, run the same thing there and replace `:80` in `deploy/Caddyfile` with your domain: Caddy then gets HTTPS certificates automatically. Set `WEB_URL` in `.env.prod` to the public address.

## Docs

- [docs/DECISIONS.md](docs/DECISIONS.md): one line per design decision and why
- [docs/LEARN.md](docs/LEARN.md): what each phase built and how it works
