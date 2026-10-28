"""Persist language and plagiarism enhancement results.

Revision ID: 007_analysis_enhancements
Revises: 006_schema_alignment
Create Date: 2026-10-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_analysis_enhancements"
down_revision: Union[str, None] = "006_schema_alignment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add JSON columns for completed enhancement results."""
    op.add_column("manuscript_analyses", sa.Column("language_info", sa.JSON(), nullable=True))
    op.add_column("manuscript_analyses", sa.Column("plagiarism_result", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove enhancement result columns."""
    op.drop_column("manuscript_analyses", "plagiarism_result")
    op.drop_column("manuscript_analyses", "language_info")
