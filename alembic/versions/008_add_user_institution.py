"""Add the author affiliation used for conflict-of-interest checks.

Revision ID: 008_user_institution
Revises: 007_analysis_enhancements
Create Date: 2026-10-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_user_institution"
down_revision: Union[str, None] = "007_analysis_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the optional institution column to users."""
    op.add_column("users", sa.Column("institution", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove the institution column."""
    op.drop_column("users", "institution")
