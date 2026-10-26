"""Use timezone-aware timestamp columns

Revision ID: 005_timezone_timestamps
Revises: 004_email_verification
Create Date: 2026-10-26

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_timezone_timestamps"
down_revision: Union[str, None] = "004_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIMESTAMP_COLUMNS = [
    ("users", "created_at"),
    ("users", "last_login"),
    ("users", "verification_token_expires_at"),
    ("manuscript_analyses", "created_at"),
    ("processing_errors", "created_at"),
    ("document_fingerprints", "created_at"),
    ("reviewers", "created_at"),
    ("reviewers", "updated_at"),
    ("reviewer_matches", "created_at"),
    ("reviewer_matches", "updated_at"),
    ("reviewer_matches", "invited_at"),
    ("reviewer_matches", "responded_at"),
]


def upgrade() -> None:
    """Store timestamps as TIMESTAMP WITH TIME ZONE."""
    for table, column in _TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Revert timestamps to TIMESTAMP WITHOUT TIME ZONE."""
    for table, column in _TIMESTAMP_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
