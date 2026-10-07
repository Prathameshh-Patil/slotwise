#!/usr/bin/env bash
# Deploy the production stack on this machine, behind one address.
#
#   ./scripts/deploy_local.sh            build and start (or update) it, then seed demo data
#   ./scripts/deploy_local.sh public     also put it on the internet (Cloudflare quick tunnel)
#   ./scripts/deploy_local.sh private    take it off the internet again
#   ./scripts/deploy_local.sh status     show the containers
#   ./scripts/deploy_local.sh logs [svc] follow logs (e.g. logs worker)
#   ./scripts/deploy_local.sh backup     dump the database to backups/
#   ./scripts/deploy_local.sh down       stop it (data is kept)
#   ./scripts/deploy_local.sh destroy    stop it and DELETE its database
#
# It runs as its own Compose project ("slotwise-prod"), so it can run next to the
# dev stack. Secrets live in .env.prod, created on first run and git-ignored.
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE=.env.prod
COMPOSE=(docker compose -p slotwise-prod -f docker-compose.prod.yml --env-file "$ENV_FILE")

create_env_file() {
  local port="${HTTP_PORT:-8080}"
  # Random secrets, generated on this machine and never committed
  umask 077
  cat > "$ENV_FILE" <<ENV
# Created by scripts/deploy_local.sh on $(date). Git-ignored. Keep it private.
POSTGRES_USER=slotwise
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_DB=slotwise
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
HTTP_PORT=$port
WEB_URL=http://localhost:$port
HOLD_MINUTES=10
ENV
  echo "Created $ENV_FILE with fresh random secrets."
}

# Older .env.prod files predate the admin password setting: add one
ensure_admin_password() {
  if ! grep -q '^SEED_ADMIN_PASSWORD=' "$ENV_FILE"; then
    echo "SEED_ADMIN_PASSWORD=$(openssl rand -hex 9)" >> "$ENV_FILE"
    echo "Added a random SEED_ADMIN_PASSWORD to $ENV_FILE."
  fi
}

admin_password() { grep '^SEED_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2; }

tunnel_url() {
  "${COMPOSE[@]}" --profile public logs tunnel 2>/dev/null \
    | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1 || true
}

port() { grep '^HTTP_PORT=' "$ENV_FILE" | cut -d= -f2; }

wait_until_healthy() {
  local url="http://localhost:$(port)/api/health"
  printf "Waiting for %s " "$url"
  for _ in $(seq 1 90); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "ok"
      return
    fi
    printf "."
    sleep 2
  done
  echo
  echo "The API didn't come up. Look at: ./scripts/deploy_local.sh logs api" >&2
  exit 1
}

case "${1:-up}" in
  up)
    [[ -f "$ENV_FILE" ]] || create_env_file
    ensure_admin_password
    "${COMPOSE[@]}" up -d --build
    wait_until_healthy
    "${COMPOSE[@]}" exec -T api python -m app.seed
    cat <<MSG

Slotwise is running at  http://localhost:$(port)
API docs:               http://localhost:$(port)/api/docs
Demo login:             demo@slotwise.dev / demo12345
Admin login:            admin@slotwise.dev / (SEED_ADMIN_PASSWORD in $ENV_FILE)
MSG
    ;;
  public)
    # Always start a fresh tunnel. A quick tunnel that lost its connection for a
    # while (e.g. the Mac slept) is deleted by Cloudflare and can't come back;
    # an old container would keep retrying it and report its dead URL.
    "${COMPOSE[@]}" --profile public rm -sf tunnel >/dev/null 2>&1 || true
    "${COMPOSE[@]}" --profile public up -d tunnel
    printf "Opening a Cloudflare tunnel "
    for _ in $(seq 1 30); do
      url="$(tunnel_url)"
      if [[ -n "$url" ]] && curl -fsS "$url/api/health" >/dev/null 2>&1; then
        echo "ok"
        echo
        echo "Public URL:  $url"
        echo "API docs:    $url/api/docs"
        echo "It works while this Mac is awake and Docker is running. Stop it: $0 private"
        echo "If the Mac sleeps for long, the URL dies: run '$0 public' again for a new one."
        exit 0
      fi
      printf "."
      sleep 3
    done
    echo
    echo "The tunnel didn't come up. Look at: $0 logs tunnel" >&2
    exit 1
    ;;
  url) tunnel_url ;;
  private) "${COMPOSE[@]}" --profile public rm -sf tunnel ;;
  status) "${COMPOSE[@]}" ps ;;
  logs) "${COMPOSE[@]}" --profile public logs -f "${@:2}" ;;
  backup)
    mkdir -p backups
    file="backups/slotwise-$(date +%Y%m%d-%H%M%S).sql"
    "${COMPOSE[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$file"
    echo "Saved $file"
    ;;
  down) "${COMPOSE[@]}" --profile public down ;;
  destroy)
    read -r -p "Delete the deployed database and all its bookings? [y/N] " answer
    [[ "$answer" == [yY] ]] && "${COMPOSE[@]}" --profile public down -v
    ;;
  *)
    sed -n '2,14p' "$0"
    exit 1
    ;;
esac
