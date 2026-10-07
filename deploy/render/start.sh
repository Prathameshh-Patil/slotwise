#!/bin/bash
# Start the three processes. If any of them exits, exit too, so the host
# notices the failure and restarts the whole container.
set -e

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
