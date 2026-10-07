"""Test setup: a real PostgreSQL database named <app db>_test, built by the migrations.

SQLite would be faster, but the double-booking guarantee depends on a Postgres
partial unique index and Postgres locking, so the tests must run on Postgres.
"""

import os

from sqlalchemy import create_engine, make_url, text

# Settings are read when app modules are imported, so set the environment first.
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-for-hs256")
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
_app_url = make_url(
    os.environ.get("DATABASE_URL", "postgresql+psycopg://slotwise:slotwise@localhost:5433/slotwise")
)
TEST_DATABASE_URL = _app_url.set(database=f"{_app_url.database}_test")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)

from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.schemas.event import EventCreate  # noqa: E402
from app.services.events import create_event  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create the test database if needed and migrate it to a clean, current schema."""
    admin = create_engine(_app_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DATABASE_URL.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_URL.database}"'))
    admin.dispose()

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    """Every test starts with empty tables."""
    yield
    with engine.begin() as conn:
        tables = "users, events, seats, orders, bookings, order_history"
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def make_user():
    """Create a user directly in the database and return their auth headers."""

    def _make(email: str = "user@example.com", is_admin: bool = False) -> dict[str, str]:
        with SessionLocal() as db:
            password = hash_password("password123")
            user = User(email=email, hashed_password=password, is_admin=is_admin)
            db.add(user)
            db.commit()
            return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _make


@pytest.fixture
def user_headers(make_user):
    return make_user()


@pytest.fixture
def admin_headers(make_user):
    return make_user("admin@example.com", is_admin=True)


@pytest.fixture
def event():
    """A future event with a 2 x 3 seat grid (A1-A3, B1-B3)."""
    with SessionLocal() as db:
        return create_event(
            db,
            EventCreate(
                title="Jazz Night",
                venue="Blue Hall",
                starts_at=datetime.now(UTC) + timedelta(days=7),
                rows=2,
                seats_per_row=3,
                price_cents=2500,
            ),
        )


@pytest.fixture
def seat_id(event):
    """The id of seat A1 of the event."""
    return event.seats[0].id
