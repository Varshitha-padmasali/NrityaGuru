"""Adopt the existing SQLAlchemy schema without dropping or rewriting data.

For a fresh database this creates every current application table. For a database
initialized by the former create_all workflow, SQLAlchemy creates only missing tables.
"""
from alembic import op

from app.db.models import Base

revision = "0001_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # This baseline may be stamped onto a database containing user data. It is
    # deliberately irreversible; use a reviewed backup/restore procedure instead.
    pass
