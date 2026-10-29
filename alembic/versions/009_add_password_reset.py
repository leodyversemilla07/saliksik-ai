"""Add the password reset token columns.

Revision ID: 009_password_reset
Revises: 008_user_institution
Create Date: 2026-10-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_password_reset"
down_revision: Union[str, None] = "008_user_institution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the password reset token columns to users."""
    op.add_column("users", sa.Column("password_reset_token", sa.String(), nullable=True))
    op.add_column("users", sa.Column("password_reset_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_users_password_reset_token",
        "users",
        ["password_reset_token"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the password reset token columns."""
    op.drop_index("ix_users_password_reset_token", table_name="users")
    op.drop_column("users", "password_reset_token_expires_at")
    op.drop_column("users", "password_reset_token")
