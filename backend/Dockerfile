# Two images from one file. `dev` (the default, used by docker-compose.yml) has
# pytest and ruff and runs as root for easy volume mounts. `prod` (used by
# docker-compose.prod.yml) has only runtime packages and runs as a normal user.
FROM python:3.12-slim AS base

# Don't write .pyc files, and print logs immediately instead of buffering them
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml .


FROM base AS prod
# Dependencies first, in their own cached layer: code edits don't trigger a reinstall
RUN pip install --no-cache-dir .
COPY . .
# If someone breaks out of the app, they land as an unprivileged user, not root
RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers"]


FROM base AS dev
RUN pip install --no-cache-dir ".[dev]"
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
