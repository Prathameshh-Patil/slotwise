#!/bin/bash
# Start the three processes. If any of them exits, exit too, so the host
# notices the failure and restarts the whole container.
set -e

# Without these the app can't start. Say exactly what's missing, because on a
# host's dashboard this log is often the only clue.
missing=()
[[ -z "${DATABASE_URL:-}" ]] && missing+=("DATABASE_URL (a Postgres connection URL)")
[[ -z "${SECRET_KEY:-}" ]] && missing+=("SECRET_KEY (any long random string)")
[[ -z "${SEED_ADMIN_PASSWORD:-}" ]] && missing+=("SEED_ADMIN_PASSWORD (the admin login password)")
if (( ${#missing[@]} )); then
  echo "Slotwise can't start. Set these environment variables:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  echo "On Render, creating the app from the Blueprint (render.yaml) sets them all." >&2
  exit 1
fi

cd /app/backend
alembic upgrade head
python -m app.seed

# One worker each: a free instance has 512 MB of memory
uvicorn app.main:app --host 127.0.0.1 --port 8000 --root-path /api --proxy-headers &
(cd /app/web && exec node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3000) &
caddy run --config /app/Caddyfile --adapter caddyfile &

wait -n || true
echo "A process exited; stopping the container so it gets restarted." >&2
exit 1
