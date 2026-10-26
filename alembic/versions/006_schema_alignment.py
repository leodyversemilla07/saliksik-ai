"""Align database schema with ORM metadata

Revision ID: 006_schema_alignment
Revises: 005_timezone_timestamps
Create Date: 2026-10-26

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_schema_alignment"
down_revision: Union[str, None] = "005_timezone_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columns that were created as nullable in 001 but are non-nullable in the
# models. Existing NULL values are backfilled with the model defaults before
# the NOT NULL constraints are applied.
_NOT_NULL_COLUMNS: tuple[tuple[str, str, sa.types.TypeEngine, str], ...] = (
    ("users", "is_active", sa.Boolean(), "true"),
    ("users", "created_at", sa.DateTime(timezone=True), "now()"),
    ("manuscript_analyses", "input_type", sa.String(10), "'text'"),
    ("manuscript_analyses", "keywords", sa.JSON(), "'[]'::json"),
    ("manuscript_analyses", "language_quality", sa.JSON(), "'{}'::json"),
    ("manuscript_analyses", "status", sa.String(20), "'PENDING'"),
    ("manuscript_analyses", "created_at", sa.DateTime(timezone=True), "now()"),
    ("processing_errors", "input_type", sa.String(10), "'text'"),
    ("processing_errors", "created_at", sa.DateTime(timezone=True), "now()"),
    ("document_fingerprints", "shingles", sa.JSON(), "'[]'::json"),
    ("document_fingerprints", "created_at", sa.DateTime(timezone=True), "now()"),
    ("reviewers", "expertise_keywords", sa.JSON(), "'[]'::json"),
    ("reviewers", "is_available", sa.Boolean(), "true"),
    ("reviewers", "current_assignments", sa.Integer(), "0"),
    ("reviewers", "max_assignments", sa.Integer(), "5"),
    ("reviewers", "created_at", sa.DateTime(timezone=True), "now()"),
    ("reviewers", "updated_at", sa.DateTime(timezone=True), "now()"),
    ("reviewer_matches", "matched_keywords", sa.JSON(), "'[]'::json"),
    ("reviewer_matches", "match_method", sa.String(50), "'keyword'"),
    ("reviewer_matches", "status", sa.String(20), "'suggested'"),
    ("reviewer_matches", "created_at", sa.DateTime(timezone=True), "now()"),
    ("reviewer_matches", "updated_at", sa.DateTime(timezone=True), "now()"),
)


def upgrade() -> None:
    """Backfill defaults, enforce NOT NULL, and remove redundant indexes."""
    for table, column, column_type, default in _NOT_NULL_COLUMNS:
        op.execute(sa.text(f'UPDATE "{table}" SET "{column}" = {default} WHERE "{column}" IS NULL'))
        op.alter_column(table, column, existing_type=column_type, nullable=False)

    # 001 created both a unique constraint and a separate unique index for
    # these columns. The constraints are the canonical uniqueness mechanism;
    # the extra indexes only duplicate storage and write cost.
    op.execute("DROP INDEX IF EXISTS ix_document_fingerprints_analysis_id")
    op.execute("DROP INDEX IF EXISTS ix_reviewers_user_id")


def downgrade() -> None:
    """Restore the nullable columns and duplicate unique indexes."""
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_document_fingerprints_analysis_id ON document_fingerprints (analysis_id)"
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_reviewers_user_id ON reviewers (user_id)")

    for table, column, column_type, _ in reversed(_NOT_NULL_COLUMNS):
        op.alter_column(table, column, existing_type=column_type, nullable=True)
