# Design decisions

One line per decision, with the reason.

- Python 3.12 in Docker (not the 3.14 on the dev machine): every library in the stack supports it well, and Docker makes the local version irrelevant.
- Monorepo (backend and frontend in one repo): one place for a reviewer to look, one CI workflow, and front-end and back-end changes ship together.
- MIT license: the simplest permissive license, standard for portfolio projects.
- Git over SSH instead of HTTPS: SSH keys aren't limited by OAuth token scopes, so pushing workflow files works without extra permissions.
- Postgres on host port 5433: another local project already uses 5432; containers still talk on 5432 internally.
- Double booking is prevented by a partial unique index on `bookings(seat_id) WHERE status IN ('held', 'confirmed')`, not by application checks: the database is the only place that sees every concurrent request, and the index turns the race into a clean unique violation (409).
- Hold, then confirm (10-minute holds): a real checkout needs time for payment, and holding a seat while the user pays is what ticket sites do. Seat status is computed from bookings and the clock, so an expired hold frees the seat even if the Celery worker is down.
- Conditional `UPDATE ... WHERE status = 'held' AND hold_expires_at > now()` to confirm, instead of read-check-write: a confirmation and an expiry racing on the same row can't both win.
- Tests run on a real Postgres database built by the Alembic migrations, not SQLite or `create_all`: the guarantee being tested is a Postgres feature, and this also tests the migrations.
- JWT in the `Authorization` header, stored in `localStorage`: simple for a separate front end and API on different ports. The trade-off is that a script injected into the page could read it; an httpOnly cookie avoids that but needs CSRF protection and same-site hosting.
- bcrypt (via the `bcrypt` package directly) for passwords: slow by design and salted. passlib is unmaintained.
- Celery with Redis for background work: confirmation emails and expiring holds shouldn't slow down or depend on an API request. Emails are logged, not sent, until a mail provider is chosen.
- Next.js front end calls the API from the browser (client components): pages show live, per-user data, so there is little to gain from server rendering, and it keeps one auth path.
- Web app on host port 3100: ports 3000 and 3001 are used by other local projects, like Postgres on 5433.
- One Dockerfile with `dev` and `prod` stages: one set of dependency steps to maintain; prod drops pytest/ruff and runs as a non-root user.
- Orders group seats: holding several seats is one transaction (all or nothing), and the order is what gets confirmed, cancelled or expired, so a group never ends up half booked.
- Seats in an order are inserted in id order: two overlapping orders then wait for each other instead of deadlocking. A deadlock is still caught and answered with 409, as a safety net.
- `order_history` is append-only, written in the same transaction as each status change: the history can't miss a change or record one that rolled back. Expiries are recorded with no actor ("the system").
- Each booking stores its price: what someone paid shouldn't change if the event's prices do.
- The orders migration converts existing bookings to one-seat orders by hand-written SQL, and a test downgrades, inserts old-style rows and upgrades again: autogenerate can't write data migrations.
- Local deployment behind Caddy on one port (8080): the browser calls `/api` on the same origin (no CORS), only the proxy is exposed, and Caddy can get HTTPS certificates automatically on a real domain.
- Public sharing through a Cloudflare quick tunnel: no account, no open ports on the router, HTTPS included. The trade-off is that it lives only while this machine runs and the URL changes on restart; a named tunnel (Cloudflare account) or a cloud server fixes both.
- Seed passwords come from the environment, and the deploy script generates a random admin password: a public site seeded with a password that is written in the repo is a site anyone can administer.
