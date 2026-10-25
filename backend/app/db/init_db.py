"""Create all tables.  Usage (from backend/):  python -m app.db.init_db

Uses create_all, which only creates MISSING tables and never alters existing ones.
When the schema starts changing often we will move to Alembic migrations.
"""
from sqlalchemy import Engine

from app.core.logging import configure_logging
from app.db.database import DatabaseNotConfiguredError, get_engine
from app.db.models import Base


def init_db(engine: Engine | None = None) -> None:
    Base.metadata.create_all(engine or get_engine())


if __name__ == "__main__":
    configure_logging("INFO")
    try:
        init_db()
        print("Tables are ready:", ", ".join(Base.metadata.tables))
    except DatabaseNotConfiguredError as exc:
        print(exc)
        raise SystemExit(1)
