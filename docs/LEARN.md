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
