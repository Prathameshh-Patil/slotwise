# Slotwise in ONE container, for hosts that run a single web service (Render's
# free plan). Caddy listens on $PORT and routes /api to FastAPI and everything
# else to Next.js, exactly like docker-compose.prod.yml, but as three processes
# in one container instead of three containers. Build context: the repo root.

FROM node:24-slim AS web-build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The browser calls /api on the same origin; Caddy forwards it to FastAPI
ENV NEXT_PUBLIC_API_URL=/api
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production
# Node runs `next start`; Caddy is the router. Both are single binaries.
COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=caddy:2 /usr/bin/caddy /usr/local/bin/caddy

WORKDIR /app/backend
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir .
COPY backend/ .

WORKDIR /app/web
COPY --from=web-build /web/package.json /web/next.config.ts ./
COPY --from=web-build /web/node_modules ./node_modules
COPY --from=web-build /web/.next ./.next

WORKDIR /app
COPY deploy/render/Caddyfile deploy/render/start.sh ./
RUN chmod +x start.sh && useradd --create-home app && chown -R app /app
USER app
EXPOSE 10000
CMD ["./start.sh"]
