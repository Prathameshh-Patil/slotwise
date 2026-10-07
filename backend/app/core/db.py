from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# pool_pre_ping checks a pooled connection is still alive before handing it out,
# so a database restart doesn't break the first request after it.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    # Store every datetime as "timestamp with time zone", so times are unambiguous
    type_annotation_map = {datetime: DateTime(timezone=True)}


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with SessionLocal() as session:
        yield session
