"""
Database configuration and session management with connection pooling.
"""

import logging

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection pool settings
POOL_SIZE = 10  # Number of persistent connections
MAX_OVERFLOW = 20  # Additional connections when pool is exhausted
POOL_TIMEOUT = 30  # Seconds to wait for available connection
POOL_RECYCLE = 1800  # Recycle connections after 30 minutes (prevents stale connections)
POOL_PRE_PING = True  # Test connections before use

# Determine if we're using SQLite (for testing) or PostgreSQL
is_sqlite = "sqlite" in settings.DATABASE_URL.lower()

# 1. Async Engine (for FastAPI)
if is_sqlite:
    # SQLite doesn't support connection pooling well in async mode
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        poolclass=NullPool,  # Disable pooling for SQLite
    )
else:
    # PostgreSQL with full connection pooling
    # Note: AsyncEngine uses AsyncAdaptedQueuePool internally, don't specify poolclass
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=POOL_PRE_PING,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# 2. Sync Engine (for Celery Tasks & Migrations)
is_sqlite_sync = "sqlite" in settings.sync_database_url.lower()

if is_sqlite_sync:
    sync_engine = create_engine(
        settings.sync_database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
else:
    sync_engine = create_engine(
        settings.sync_database_url,
        pool_pre_ping=POOL_PRE_PING,
        pool_size=POOL_SIZE // 2,  # Fewer connections for background tasks
        max_overflow=MAX_OVERFLOW // 2,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


# Connection pool event listeners for monitoring
@event.listens_for(sync_engine, "connect")
def on_connect(dbapi_conn, connection_record):
    """Called when a new connection is created."""
    logger.debug("New database connection established")


@event.listens_for(sync_engine, "checkout")
def on_checkout(dbapi_conn, connection_record, connection_proxy):
    """Called when a connection is retrieved from the pool."""
    logger.debug("Connection checked out from pool")


@event.listens_for(sync_engine, "checkin")
def on_checkin(dbapi_conn, connection_record):
    """Called when a connection is returned to the pool."""
    logger.debug("Connection returned to pool")


async def get_db():
    """Async database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_pool_status() -> dict:
    """Get current connection pool status."""
    try:
        pool = sync_engine.pool
        return {
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
            "invalid": pool.invalidatedcount()
            if hasattr(pool, "invalidatedcount")
            else 0,
        }
    except Exception as e:
        logger.debug(f"Could not get pool status: {e}")
        return {"status": "unavailable"}
