"""Add practice state and reference-sequence storage idempotently."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.db.models import ReferenceSequence

revision = "0002_practice_reference"
down_revision = "0001_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("practice_sessions")}
    if "status" not in columns:
        with op.batch_alter_table("practice_sessions") as batch:
            batch.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="created"))
    if "failure_reason" not in columns:
        with op.batch_alter_table("practice_sessions") as batch:
            batch.add_column(sa.Column("failure_reason", sa.String(length=80), nullable=True))
    indexes = {index["name"] for index in inspect(bind).get_indexes("practice_sessions")}
    if "ix_practice_sessions_status" not in indexes:
        op.create_index("ix_practice_sessions_status", "practice_sessions", ["status"], unique=False)
    checks = {constraint.get("name") for constraint in inspect(bind).get_check_constraints("practice_sessions")}
    if "ck_practice_session_status" not in checks:
        with op.batch_alter_table("practice_sessions") as batch:
            batch.create_check_constraint(
                "ck_practice_session_status",
                "status IN ('created', 'uploaded', 'processing', 'evaluated', 'failed')",
            )
    ReferenceSequence.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("This migration is intentionally irreversible because it may contain reviewed references and practice history.")
