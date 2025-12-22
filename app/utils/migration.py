"""
Alembic database migration script.
"""
from alembic import command
from alembic.config import Config
import os

def create_migration(message: str):
    """Create a new migration."""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)

def run_migrations():
    """Run all pending migrations."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

if __name__ == "__main__":
    run_migrations()
