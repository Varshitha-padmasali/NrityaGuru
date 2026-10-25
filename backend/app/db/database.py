"""Engine and session management. The database URL is never logged or put in errors."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_configured:
        raise DatabaseNotConfiguredError("DATABASE_URL is not set. Copy .env.example to .env.")
    return create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
