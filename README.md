# Slotwise

An event booking platform where users pick a seat and book it, and two people clicking the same seat at the same moment can never both get it.

Built with Next.js, FastAPI, PostgreSQL, Celery and Redis.

## How double booking is prevented

Picking a seat creates a **hold**: a `bookings` row with status `held` that expires after 10 minutes unless it is confirmed. The bookings table has a partial unique index:

```sql
CREATE UNIQUE INDEX uq_bookings_one_active_per_seat
  ON bookings (seat_id) WHERE status IN ('held', 'confirmed');
```

So the database itself allows at most one active booking per seat. When two requests try to hold the same seat at once, both inserts reach Postgres. The second waits for the first to commit and then fails with a unique violation, and the API answers `409 Conflict`. Nothing in the application code has to "check, then insert", which is exactly the pattern that breaks under concurrency.

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
| `backend/app/services` | Business logic: booking rules live in `services/bookings.py` |
| `backend/app/routers` | HTTP endpoints, thin wrappers around the services |
| `backend/app/tasks` | Celery app and background tasks |
| `backend/alembic` | Database migrations |
| `frontend/app` | Next.js pages: events, seat map, login, bookings, admin |
| `scripts/race_demo.py` | Fires N simultaneous holds at one seat against the live API |

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
| POST | `/seats/{id}/hold` | user | Hold a seat (201, or 409 if taken) |
| POST | `/bookings/{id}/confirm` | owner | Turn a live hold into a booking |
| POST | `/bookings/{id}/cancel` | owner | Release a hold or cancel a booking |
| GET | `/bookings/me` | user | My bookings |

## Production

`docker-compose.prod.yml` builds lean images (no dev tools, non-root user, no code mounts, no reload) and refuses to start without real secrets:

```
# .env.prod: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, SECRET_KEY,
#            API_URL (public API address), WEB_URL (public site address)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Put a TLS-terminating reverse proxy (Caddy, nginx, or your platform's load balancer) in front of ports 8000 and 3000.

## Docs

- [docs/DECISIONS.md](docs/DECISIONS.md): one line per design decision and why
- [docs/LEARN.md](docs/LEARN.md): what each phase built and how it works
