"""Add email verification fields to users table

Revision ID: 004_email_verification
Revises: 003_roles
Create Date: 2026-01-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_email_verification'
down_revision: Union[str, None] = '003_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default='0')
    )
    op.add_column(
        'users',
        sa.Column('verification_token', sa.String(), nullable=True)
    )
    op.add_column(
        'users',
        sa.Column('verification_token_expires_at', sa.DateTime(), nullable=True)
    )
    op.create_index(
        op.f('ix_users_verification_token'),
        'users',
        ['verification_token'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_users_verification_token'), table_name='users')
    op.drop_column('users', 'verification_token_expires_at')
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'is_email_verified')
