"""Initial schema - all models

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_api_key', 'users', ['api_key'], unique=True)

    # Manuscript Analyses table
    op.create_table(
        'manuscript_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('input_type', sa.String(10), default='text'),
        sa.Column('manuscript_text', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('keywords', sa.JSON(), default=list),
        sa.Column('language_quality', sa.JSON(), default=dict),
        sa.Column('detected_language', sa.String(10), nullable=True),
        sa.Column('citation_analysis', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), default='PENDING'),
        sa.Column('task_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], )
    )
    op.create_index('ix_manuscript_analyses_id', 'manuscript_analyses', ['id'], unique=False)
    op.create_index('ix_manuscript_analyses_user_id', 'manuscript_analyses', ['user_id'], unique=False)
    op.create_index('ix_manuscript_analyses_status', 'manuscript_analyses', ['status'], unique=False)
    op.create_index('ix_manuscript_analyses_task_id', 'manuscript_analyses', ['task_id'], unique=True)
    op.create_index('ix_manuscript_analyses_created_at', 'manuscript_analyses', ['created_at'], unique=False)

    # Processing Errors table
    op.create_table(
        'processing_errors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('error_type', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('input_type', sa.String(10), default='text'),
        sa.Column('input_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_processing_errors_id', 'processing_errors', ['id'], unique=False)
    op.create_index('ix_processing_errors_created_at', 'processing_errors', ['created_at'], unique=False)

    # Document Fingerprints table (for plagiarism detection)
    op.create_table(
        'document_fingerprints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('fingerprint_hash', sa.LargeBinary(), nullable=False),
        sa.Column('shingles', sa.JSON(), default=list),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['manuscript_analyses.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('analysis_id')
    )
    op.create_index('ix_document_fingerprints_id', 'document_fingerprints', ['id'], unique=False)
    op.create_index('ix_document_fingerprints_analysis_id', 'document_fingerprints', ['analysis_id'], unique=True)
    op.create_index('ix_document_fingerprints_created_at', 'document_fingerprints', ['created_at'], unique=False)

    # Reviewers table
    op.create_table(
        'reviewers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('expertise_keywords', sa.JSON(), default=list),
        sa.Column('expertise_embedding', sa.LargeBinary(), nullable=True),
        sa.Column('expertise_description', sa.String(1000), nullable=True),
        sa.Column('institution', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('orcid_id', sa.String(50), nullable=True),
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('current_assignments', sa.Integer(), default=0),
        sa.Column('max_assignments', sa.Integer(), default=5),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('orcid_id')
    )
    op.create_index('ix_reviewers_id', 'reviewers', ['id'], unique=False)
    op.create_index('ix_reviewers_user_id', 'reviewers', ['user_id'], unique=True)
    op.create_index('ix_reviewers_is_available', 'reviewers', ['is_available'], unique=False)

    # Reviewer Matches table
    op.create_table(
        'reviewer_matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=False),
        sa.Column('matched_keywords', sa.JSON(), default=list),
        sa.Column('match_method', sa.String(50), default='keyword'),
        sa.Column('status', sa.String(20), default='suggested'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('invited_at', sa.DateTime(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['manuscript_analyses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['reviewers.id'], ondelete='CASCADE')
    )
    op.create_index('ix_reviewer_matches_id', 'reviewer_matches', ['id'], unique=False)
    op.create_index('ix_reviewer_matches_analysis_id', 'reviewer_matches', ['analysis_id'], unique=False)
    op.create_index('ix_reviewer_matches_reviewer_id', 'reviewer_matches', ['reviewer_id'], unique=False)
    op.create_index('ix_reviewer_matches_status', 'reviewer_matches', ['status'], unique=False)
    op.create_index('ix_reviewer_matches_created_at', 'reviewer_matches', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('reviewer_matches')
    op.drop_table('reviewers')
    op.drop_table('document_fingerprints')
    op.drop_table('processing_errors')
    op.drop_table('manuscript_analyses')
    op.drop_table('users')
