"""Add performance indexes for common queries

Revision ID: 002_indexes
Revises: 001_initial
Create Date: 2026-01-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_indexes'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for user's analysis history (common query pattern)
    op.create_index(
        'ix_manuscript_analyses_user_status',
        'manuscript_analyses',
        ['user_id', 'status'],
        unique=False
    )
    
    # Composite index for listing analyses by date (pagination)
    op.create_index(
        'ix_manuscript_analyses_user_created',
        'manuscript_analyses',
        ['user_id', 'created_at'],
        unique=False
    )
    
    # Index for finding available reviewers quickly
    op.create_index(
        'ix_reviewers_available_assignments',
        'reviewers',
        ['is_available', 'current_assignments'],
        unique=False
    )
    
    # Composite index for reviewer match queries
    op.create_index(
        'ix_reviewer_matches_analysis_status',
        'reviewer_matches',
        ['analysis_id', 'status'],
        unique=False
    )
    
    # Composite index for reviewer's matches
    op.create_index(
        'ix_reviewer_matches_reviewer_status',
        'reviewer_matches',
        ['reviewer_id', 'status'],
        unique=False
    )
    
    # Index for match score ordering (finding best matches)
    op.create_index(
        'ix_reviewer_matches_score',
        'reviewer_matches',
        ['analysis_id', 'match_score'],
        unique=False
    )
    
    # Index for error tracking by type and date
    op.create_index(
        'ix_processing_errors_type_date',
        'processing_errors',
        ['error_type', 'created_at'],
        unique=False
    )
    
    # Index for active users (login queries)
    op.create_index(
        'ix_users_active',
        'users',
        ['is_active'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_users_active', table_name='users')
    op.drop_index('ix_processing_errors_type_date', table_name='processing_errors')
    op.drop_index('ix_reviewer_matches_score', table_name='reviewer_matches')
    op.drop_index('ix_reviewer_matches_reviewer_status', table_name='reviewer_matches')
    op.drop_index('ix_reviewer_matches_analysis_status', table_name='reviewer_matches')
    op.drop_index('ix_reviewers_available_assignments', table_name='reviewers')
    op.drop_index('ix_manuscript_analyses_user_created', table_name='manuscript_analyses')
    op.drop_index('ix_manuscript_analyses_user_status', table_name='manuscript_analyses')
