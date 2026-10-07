"""Fill a fresh database with an admin, a demo user and a few events.

Run with: docker compose exec api python -m app.seed
Safe to run twice: it skips anything that already exists.

Passwords come from SEED_ADMIN_PASSWORD and SEED_DEMO_PASSWORD when set (a
public deployment must set at least the admin one); otherwise the development
defaults below are used. When a password is set, existing users are updated
to it, so changing it and re-running the seed rotates it.
"""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Event, User
from app.schemas.event import EventCreate
from app.services.events import create_event

# (email, env var that overrides the password, development default, is_admin)
USERS = [
    ("admin@slotwise.dev", "SEED_ADMIN_PASSWORD", "admin12345", True),
    ("demo@slotwise.dev", "SEED_DEMO_PASSWORD", "demo12345", False),
]


def main() -> None:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    events = [
        EventCreate(
            title="Midnight Jazz Quartet",
            description="Four players, one long night of standards and new tunes.",
            venue="Blue Room, Pune",
            starts_at=now + timedelta(days=5, hours=3),
            rows=6,
            seats_per_row=10,
            price_cents=1800,
        ),
        EventCreate(
            title="Stand-up Saturday",
            description="Five comedians, ten minutes each, no hecklers please.",
            venue="The Laugh Store, Mumbai",
            starts_at=now + timedelta(days=9, hours=1),
            rows=8,
            seats_per_row=12,
            price_cents=1200,
        ),
        EventCreate(
            title="Indie Film Premiere",
            description="A screening followed by a Q&A with the director.",
            venue="Screen 2, Bengaluru",
            starts_at=now + timedelta(days=14),
            rows=5,
            seats_per_row=8,
            price_cents=900,
        ),
    ]

    with SessionLocal() as db:
        for email, env_var, default, is_admin in USERS:
            configured = os.environ.get(env_var)
            password = configured or default
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                hashed = hash_password(password)
                db.add(User(email=email, hashed_password=hashed, is_admin=is_admin))
                print(f"Created user {email}")
            elif configured:
                user.hashed_password = hash_password(configured)
                print(f"Set password for {email} from {env_var}")
        db.commit()

        for body in events:
            if not db.scalar(select(Event).where(Event.title == body.title)):
                create_event(db, body)
                print(f"Created event {body.title}")


if __name__ == "__main__":
    main()
