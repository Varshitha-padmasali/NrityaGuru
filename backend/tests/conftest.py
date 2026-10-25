import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base


@pytest.fixture
def db_session():
    """In-memory SQLite for fast, isolated tests.

    The app targets PostgreSQL; these models use only portable types. Foreign keys
    are switched on because SQLite ignores them by default.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
