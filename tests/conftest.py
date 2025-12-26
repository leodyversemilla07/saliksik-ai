import asyncio
import os
import sys
from unittest.mock import MagicMock

# MOCKING HEAVY DEPENDENCIES BEFORE IMPORTS
mocks = [
    "spacy",
    "numpy",
    "pandas",
    "sklearn",
    "sklearn.metrics.pairwise",
    "transformers",
    "torch",
    "sentence_transformers",
    "nltk",
    "nltk.tokenize",
    "langdetect",
    "datasketch",
    "xxhash"
]

for m in mocks:
    sys.modules[m] = MagicMock()

# Mock internal services that depend on ML
sys.modules["app.services.ai_processor"] = MagicMock()
sys.modules["app.services.reviewer_matcher"] = MagicMock()
sys.modules["app.services.plagiarism_checker"] = MagicMock()

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base, get_db

from main import app
from app.models.user import User

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_suite.db"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, future=True, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Cleanup file
    if os.path.exists("./test_suite.db"):
        os.remove("./test_suite.db")

@pytest.fixture(scope="function")
async def db_session(db_engine):
    async_session = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )

    async with async_session() as session:
        yield session
        # Rollback after each test to keep DB clean
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session):
    # Override the get_db dependency to use our test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
