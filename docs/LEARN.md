# Learning notes

What we built in each phase, why it is designed that way, and what the alternative would have been.

## Phase 0: Machine setup and repository

**What we built.** An empty but organised project: the folder layout for the back end, front end, scripts and docs; an MIT license; a `.gitignore`; an `.env.example`; and a public GitHub repo with `main` pushed to it.

**Why it is designed this way.**
- *Monorepo.* The back end and front end live in one repository, so one pull request can change both sides of a feature and one CI workflow tests everything. The alternative is two repos, which suits big teams that release separately but adds coordination work for no benefit here.
- *`.gitkeep` files.* Git tracks files, not folders, so an empty folder disappears from the repo. An empty placeholder file keeps the structure visible on GitHub. We delete them as real files arrive.
- *`.gitignore` before the first commit.* `.env` holds secrets (database passwords, the JWT signing key). Ignoring it from day one means a secret can never be committed by accident. Removing a secret from git history afterwards is painful, and it should be treated as leaked anyway. `.env.example` is committed instead: it lists the variable names with no real values.
- *SSH for git pushes.* The GitHub CLI login lacked the `workflow` permission that GitHub requires before accepting files under `.github/workflows/`. We switched git to an SSH key: the private key stays on the laptop, the public key is registered on GitHub, and pushes are authenticated by proving we hold the private key. The alternative was to grant the CLI token the extra permission (`gh auth refresh -s workflow`).

**Git commands used.**
- `git init -b main`: turns a folder into a git repository, with the first branch named `main`.
- `git add .`: stages every changed file, which means choosing what goes into the next snapshot.
- `git commit -m "..."`: saves the staged files as a snapshot with a message.
- `git remote set-url origin <url>`: `origin` is the nickname for the GitHub copy of the repo. This changes the address git uses to reach it.
- `git push -u origin main`: uploads local commits on `main` to GitHub. `-u` remembers the pairing, so later a plain `git push` is enough.
- `gh repo create`: creates the repository on GitHub from the terminal.

**How to check it.** Open https://github.com/Prathameshh-Patil/slotwise, then run `git status` in `~/slotwise` and expect "nothing to commit, working tree clean".

## Phase 1: Back-end skeleton, Docker and CI

**What we built.** A FastAPI app with one endpoint (`GET /health`), configuration read from environment variables, a Docker image for the API, a Compose file that runs the API next to PostgreSQL, one pytest test, ruff for lint and formatting, and a GitHub Actions workflow that runs lint and tests on every push and pull request.

**How to run it.**
```
cp .env.example .env          # first time only
docker compose up --build     # starts db, waits until it is healthy, then starts api
```
Open http://localhost:8000/health and http://localhost:8000/docs. Run checks inside the container:
```
docker compose exec api pytest -v
docker compose exec api ruff check .
docker compose exec api ruff format .     # fixes formatting
docker compose down                       # stop (add -v to also delete the database volume)
```

**Why it is designed this way.**
- *Settings from the environment (`app/core/config.py`).* `Settings` is a pydantic class: each field is read from the env var of the same name and type-checked at startup. A wrong or missing value crashes the app immediately instead of failing later on a request. The same code runs locally, in CI and in production; only the environment changes, and no secret lives in git. The alternative, hard-coding values or keeping a `config.py` per environment, puts secrets in the repo.
- *Dockerfile layer order.* Docker caches each step. We copy `pyproject.toml` and install dependencies *before* copying the code, so a code change reuses the cached install layer and rebuilds take seconds. Copying everything first would reinstall every package on every edit.
- *`pyproject.toml` with `py-modules = []`.* The back end is an app, not a library, so there is nothing to package. `pyproject.toml` only lists dependencies and configures pytest and ruff. That's why `pip install ".[dev]"` works with only that one file copied.
- *Compose details.* `depends_on: condition: service_healthy` makes the API wait until `pg_isready` says PostgreSQL accepts connections. Plain `depends_on` only waits for the container to *start*, and Postgres needs a few seconds after that. Inside Compose, containers reach each other by service name, so the API's `DATABASE_URL` uses host `db`, not `localhost`. To a container, `localhost` means the container itself. The `./backend:/app` volume plus `--reload` means edits on the Mac restart the server instantly without a rebuild. The `pgdata` named volume keeps database data when containers are recreated.
- *Port 5433.* Another project already uses 5432 on this Mac. The mapping `"5433:5432"` means Mac port 5433 leads to container port 5432. Only tools on the Mac (psql, scripts) use 5433.
- *Dev tools in the image.* pytest and ruff are installed in the same image, so tests run with `docker compose exec`. The cost is a slightly larger image. The alternative is a separate production stage without dev tools, which we can add in Phase 9 if image size matters.
- *CI on a fresh machine.* CI catches "works on my machine" problems: a dependency you forgot to list, a file you forgot to commit. It runs on `push` and `pull_request`, so a PR branch gets two identical runs. That's harmless, and it's what the brief asked for. The alternative is to trigger `push` only on `main`.
- *Known warning.* Starlette deprecates `httpx` in its test client in favour of `httpx2`. We kept `httpx` for now; the test passes and it's only a warning.

**Git commands used.**
- `git checkout -b <name>`: create a new branch and switch to it.
- `git push -u origin <branch>`: publish the branch to GitHub and remember the pairing.
- `gh pr create`: open a pull request from the current branch into `main`.
- `gh pr checks --watch`: follow the CI status of a PR until it finishes.
- `gh pr merge --merge --delete-branch`: merge the PR with a merge commit, keeping the small commits in history, and delete the branch.

## Phase 2: Database models and migrations

**What we built.** Four tables (`users`, `events`, `seats`, `bookings`) as SQLAlchemy models in `app/models/`, a database session per request (`app/core/db.py`), and Alembic migrations in `backend/alembic/`. The API runs `alembic upgrade head` every time it starts.

**Why it is designed this way.**
- *Seats are rows, and "taken" is not a column on the seat.* Whether a seat is free comes from its bookings: a seat is taken if it has a confirmed booking, or a held booking whose hold hasn't expired. Storing a `status` on the seat as well would give two sources of truth that can disagree.
- *The partial unique index.* `UNIQUE (seat_id) WHERE status IN ('held', 'confirmed')` means a seat can have any number of old cancelled or expired bookings but only one active one. This one line is what makes double booking impossible (see Phase 4).
- *Migrations instead of `create_all`.* `Base.metadata.create_all()` can create tables but can never change them. Alembic records each schema change as a numbered script, so every database (yours, CI's, production's) can be upgraded step by step. `alembic revision --autogenerate` compares the models with the database and writes the script. Always read it: autogenerate missed dropping the `booking_status` enum type in `downgrade()`, so we added that by hand.
- *Timezone-aware timestamps.* Every `datetime` column is `timestamp with time zone`. A naive time like "20:00" is ambiguous once servers and users are in different zones.

**How to check it.**
```
docker compose exec api alembic current        # which migration the database is at
docker compose exec api alembic check          # "No new upgrade operations" = models and migrations agree
docker compose exec db psql -U slotwise -c '\d bookings'
```
After changing a model: `docker compose exec api alembic revision --autogenerate -m "describe the change"`, read the file, then `alembic upgrade head`.

## Phase 3: Authentication

**What we built.** `POST /auth/register`, `POST /auth/login` (returns a JWT) and `GET /auth/me`. Routes declare who may call them with type aliases from `app/core/deps.py`: `CurrentUser`, `AdminUser`, `OptionalUser`.

**Why it is designed this way.**
- *bcrypt.* We never store passwords, only a bcrypt hash. bcrypt adds a random salt to each hash, so two users with the same password get different hashes, and it is deliberately slow, so guessing passwords from a leaked database is expensive. It only reads the first 72 bytes, so longer passwords are rejected rather than silently cut short.
- *JWT.* After login, the API hands back a token signed with `SECRET_KEY` that says "user 7, valid until 11:00". On each request the API checks the signature instead of looking up a session, so any API instance can verify it. The downside: a token can't be revoked before it expires, which is why it only lasts 60 minutes.
- *Same error for unknown email and wrong password.* Otherwise the login form tells an attacker which emails have accounts.
- *Emails are lower-cased.* `Ana@x.com` and `ana@x.com` are the same person.
- *Dependencies.* FastAPI runs `get_current_user` before the route and passes the user in. If the token is missing or bad, the route never runs. The `/docs` page uses the same setup for its "Authorize" button.

**How to check it.** Open http://localhost:8000/docs, register through `/auth/register`, click "Authorize", log in, then call `/auth/me`.

## Phase 4: Events, seat map and race-safe booking

**What we built.** Admins create an event with a grid of seats. Anyone can list events and see the seat map. Logged-in users **hold** a seat (10 minutes), then **confirm** or **cancel** it. All booking rules live in `app/services/bookings.py`; the routers only translate between HTTP and those functions.

**The race, and why the obvious fix doesn't work.** The naive version is: "if the seat has no active booking, insert one". Two requests arriving together both run the check, both see the seat free, and both insert. Adding a Python lock doesn't help either: it only covers one process, and production runs several. The only component that sees every request is the database, so the rule lives there as the partial unique index. Both inserts reach Postgres. The second one waits until the first commits, then fails with `UniqueViolation`, which the API turns into `409 Conflict`. There is no window in which both can succeed.

**Other details.**
- *Lapsed holds.* An expired hold still counts for the index until its status changes, so `hold_seat` first marks any lapsed hold on that seat `expired`, in the same transaction. The seat map compares `hold_expires_at` with the current time, so a seat shows as free the moment its hold lapses, whether or not the background worker has run.
- *Confirm is one conditional UPDATE.* `UPDATE ... SET status='confirmed' WHERE id=? AND status='held' AND hold_expires_at > now()`. If the expiry task touches the same row at the same moment, Postgres row locking lets only one of them change it. "Read the row, check it in Python, then write" would have the same race as above.
- *404 for other people's bookings, not 403.* A 403 would confirm that booking 42 exists.

**Testing it.** `tests/test_concurrency.py` starts 12 threads, each with its own database connection, and holds them at a `threading.Barrier` so they all fire at the same instant. Exactly one must win. To prove the test means something, we ran it once with the index dropped: several threads "won" the same seat and both tests failed. Tests use a separate `slotwise_test` database that `conftest.py` creates and migrates, so they never touch your dev data.

**How to check it.**
```
docker compose exec api pytest tests/test_concurrency.py -v
python3 scripts/race_demo.py --users 100      # against the running API
```

## Phase 5: Background tasks with Celery and Redis

**What we built.** A Celery worker and a Celery beat scheduler, both running the same code as the API, with Redis as the queue between them. Two tasks in `app/tasks/bookings.py`: `send_booking_confirmation` (logs the email it would send) and `release_expired_holds` (beat queues it every 30 seconds).

**Why it is designed this way.**
- *Why a queue.* Sending email can take seconds or fail. If the API sent it inline, a slow mail server would make "Confirm" slow, and a failure would turn a successful booking into an error. Instead the API puts a small message on Redis ("email booking 12") and answers straight away. The worker picks it up, and retries with growing delays if it fails.
- *The task gets an id, not an object.* By the time the worker runs, the data may have changed, so the task loads the current row itself.
- *`task_acks_late`.* The message is only removed from the queue once the task finishes, so a worker that crashes mid-task doesn't lose it.
- *Beat is a separate process.* Beat is just a clock that queues tasks; the worker runs them. Run exactly one beat, or every task gets scheduled twice.
- *Correctness never depends on the worker.* Seats free up on time even if the worker is down (Phase 4). The expiry task only tidies the stored status, e.g. for "My bookings".
- *Tests run tasks inline.* `CELERY_TASK_ALWAYS_EAGER=true` makes `.delay()` run the task immediately, so the tests don't need Redis.

**How to check it.**
```
docker compose logs -f worker      # confirm a booking and watch "Email to ..." appear
docker compose logs -f beat        # "Scheduler: Sending due task release-expired-holds" every 30 s
```

## Phase 6: Next.js front end

**What we built.** A Next.js 16 app (App Router, TypeScript, Tailwind 4) in `frontend/` with pages for events, the seat map, login and sign-up, my bookings, and creating events (admins only). It runs in Compose at http://localhost:3100.

**Why it is designed this way.**
- *Client components that call the API.* Every page shows live, per-user data (which seats are yours, your countdown), so the browser fetches it directly from FastAPI using the token. `lib/api.ts` is the only place that knows the API's address and turns error responses into readable messages.
- *Auth context.* `lib/auth.tsx` keeps the logged-in user in React context, so the header and every page agree on who is logged in. On load it asks `/auth/me` whether the saved token still works.
- *Polling the seat map every 3 seconds.* It's the simplest way to see other people's picks. WebSockets would be instant but add a second protocol to run and secure. The server still has the final say: if the map is stale, the hold gets a 409 and the page says "Too slow!".
- *Derived state over effects.* Whether a hold is still live is computed from the countdown on every render, not stored and updated by an effect. The new React lint rules flag `setState` inside effects because it causes extra renders and states that disagree.
- *Suspense around URL reads.* With `cacheComponents` on, Next prerenders as much as it can at build time. Anything that reads the URL (`usePathname`, `useSearchParams`, `params`) is only known per request, so it must sit inside `<Suspense>`, or the build fails.
- *`?next=` redirect after login only accepts paths starting with a single `/`.* Otherwise a crafted link like `/login?next=https://evil.example` would send users to another site after they log in.
- *CORS.* The page (localhost:3100) and API (localhost:8000) are different origins, so the browser blocks responses unless the API lists the page's origin in `CORS_ORIGINS`.

**How to check it.** Log in as `demo@slotwise.dev` / `demo12345`, open an event, pick a seat, hold it, confirm it. Open the same event in a private window as another user and watch the seat turn grey within 3 seconds.

## Phase 7: CI for the whole stack, and production images

**What we built.** CI now runs the backend tests against a Postgres service, checks that migrations match the models, and has a front-end job (lint, type-check, build). The backend Dockerfile has `dev` and `prod` stages, the front end has `Dockerfile.prod`, and `docker-compose.prod.yml` runs the production stack.

**Why it is designed this way.**
- *Postgres in CI.* GitHub Actions `services:` starts a Postgres container next to the job, so CI runs exactly the tests you run locally.
- *`alembic check` in CI.* Fails if someone changes a model but forgets to generate a migration.
- *Multi-stage builds.* The prod API image skips pytest and ruff, and runs as a normal user, so a break-in doesn't get root in the container. The front-end image builds in one stage and copies only the result into the next.
- *`NEXT_PUBLIC_API_URL` is a build argument.* Next.js writes `NEXT_PUBLIC_*` values into the browser JavaScript during `next build`, so changing the API address means rebuilding the image.
- *`${SECRET_KEY:?set SECRET_KEY}` in the prod Compose file.* Compose refuses to start if it's missing, instead of quietly running production with a development secret.
- *No database port in production.* Only the containers can reach Postgres.

**What's left for a real launch.** A real email provider in `send_booking_confirmation`, payments in `confirm_booking`, a reverse proxy with HTTPS, database backups, and rate limiting on login.

## Phase 8: Multi-seat orders and booking history

**What we built.** Users pick up to 10 seats and hold them all at once as an **order**. `order_history` records every change to every order. My bookings shows each order's seats, prices, timestamps and a timeline; admins get an All bookings page with filters (event, status, email), totals, and the power to cancel any order.

**Why it is designed this way.**
- *All or nothing.* All the seat inserts for an order run in one transaction. If the unique index rejects any one of them, the whole transaction rolls back, so the user never ends up with half the seats they wanted. The error message names the seats that were taken, and the page keeps the others selected.
- *Deadlocks, and why we sort.* Imagine A wants seats 1 and 2 and B wants 2 and 1. A inserts seat 1 and B inserts seat 2; now A waits for B's seat 2 and B waits for A's seat 1, forever. Postgres notices after about a second and kills one of them. Inserting seats in id order means both start with seat 1, so one simply waits behind the other. We still catch `DeadlockDetected` and answer 409, in case some other path ever locks in a different order. (Our concurrency test couldn't make a deadlock happen even without sorting, because two-seat inserts finish too fast. So the test checks the outcome, not the sorting.)
- *Status on the order and on each booking.* The order's status is what users see and what confirm/expire update, with a conditional `UPDATE ... RETURNING` as before. Each booking's status is what the unique index looks at. Both always change in the same transaction.
- *An append-only history table instead of updating rows in place.* `orders` only knows where an order is now. `order_history` keeps every step: who did it, when, and a readable description. Because history rows are written in the same transaction as the change, a history row exists exactly when the change happened. Expiries have no actor, shown as "the system".
- *Price snapshot.* `bookings.price_cents` is copied from the seat at booking time. Seat prices can change later; receipts mustn't.
- *Data migration.* Alembic's autogenerate only sees schema, not data. The migration was written by hand: create the new tables, add the new columns as nullable, fill them from the old data with SQL, then make them `NOT NULL` and drop the old columns. Every existing booking became a one-seat order with the same id, so `orders_id_seq` had to be moved past those ids. `tests/test_migrations.py` downgrades the test database, inserts old-style rows, upgrades, and checks the result.

**How to check it.** Pick three seats, hold them, then open My bookings and expand "History and details". As admin, open All bookings and filter by status. In SQL: `docker compose exec db psql -U slotwise -c 'SELECT * FROM order_history ORDER BY id DESC LIMIT 10'`.

## Phase 9: Deploying locally in production mode

**What we built.** `./scripts/deploy_local.sh` builds the production images and runs the full stack behind a **Caddy** reverse proxy at http://localhost:8080. It also checks health, shows logs, backs up the database, and stops or deletes the stack.

**Why it is designed this way.**
- *A reverse proxy in front.* In a real deployment users reach one address. Caddy forwards `/api/...` to FastAPI (stripping `/api`) and everything else to Next.js. The browser calls `/api` on the same origin, so CORS doesn't apply and the front end doesn't need to know a hostname. On a real server, putting a domain name in the Caddyfile makes Caddy get and renew HTTPS certificates by itself.
- *`--root-path /api`.* FastAPI doesn't see the `/api` prefix (Caddy removed it), but its docs page must link to `/api/openapi.json`. `root_path` tells it where it is mounted.
- *A separate Compose project (`-p slotwise-prod`).* Container names, networks and volumes get their own prefix, so the deployment runs next to the dev stack without touching its database.
- *Secrets generated on the machine.* The script writes `.env.prod` with random passwords using `openssl rand`, readable only by your user (`umask 077`), and git-ignored. Nothing secret is in the repo.
- *Health before seeding.* `up -d` returns once containers start, not once they work. The script polls `/api/health` before seeding, and the `api` service has a Docker healthcheck too.
- *Backups.* `backup` runs `pg_dump` inside the database container and saves the SQL to `backups/` (git-ignored). Restore with `psql < file.sql` into an empty database.

**How to check it.**
```
./scripts/deploy_local.sh            # then open http://localhost:8080
./scripts/deploy_local.sh status
python3 scripts/race_demo.py --api http://localhost:8080/api
```
