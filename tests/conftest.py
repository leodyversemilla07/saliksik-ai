import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Set required env vars BEFORE any app imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long-for-testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_suite.db")
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///./test_suite.db")

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
ai_processor_mock = MagicMock()
# Configure the mock to return serializable data
ai_processor_mock.ManuscriptPreReviewer.return_value.generate_report.return_value = {
    "summary": "This is a mocked summary.",
    "keywords": ["mock", "test"],
    "language_quality": {"score": 100, "issues": []}
}
sys.modules["app.services.ai_processor"] = ai_processor_mock

# Mock reviewer_matcher with proper return values
reviewer_matcher_mock = MagicMock()
# create_expertise_embedding should return None (not bytes) since we mock sentence_transformers
reviewer_matcher_mock.get_reviewer_matcher.return_value.create_expertise_embedding.return_value = None
reviewer_matcher_mock.get_reviewer_matcher.return_value.calculate_keyword_similarity.return_value = (0.5, ["test"])
reviewer_matcher_mock.get_reviewer_matcher.return_value.find_matching_reviewers_async.return_value = []
sys.modules["app.services.reviewer_matcher"] = reviewer_matcher_mock

sys.modules["app.services.plagiarism_checker"] = MagicMock()

# Mock the Celery task so .delay() returns immediately instead of running
celery_task_mock = MagicMock()
celery_task_mock.delay.return_value = MagicMock(id="fake-task-id-123")
sys.modules["app.tasks.analysis"] = celery_task_mock

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base, get_db

from main import app
from app.models.user import User

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_suite.db"

# Configure Celery for testing (Eager mode)
from app.celery_app import celery_app
celery_app.conf.update(
    broker_url='memory://',
    result_backend='cache+memory://',
    task_always_eager=True,
    task_eager_propagates=True
)

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

    # Cleanup file (with retry for Windows file locking)
    if os.path.exists("./test_suite.db"):
        try:
            os.remove("./test_suite.db")
        except PermissionError:
            pass  # File may still be locked on Windows, ignore

@pytest.fixture(scope="session")
def sync_db_engine():
    """Synchronous engine for Celery tasks in eager mode."""
    # Must point to the same file as TEST_DATABASE_URL
    SYNC_TEST_DB_URL = "sqlite:///./test_suite.db"
    engine = create_engine(SYNC_TEST_DB_URL, echo=False)
    return engine

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

@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for all tests — tested separately in test_rate_limit.py."""
    with patch('app.core.rate_limit.rate_limiter') as mock_rl:
        mock_rl.is_allowed.return_value = (True, 999)
        yield


@pytest.fixture(scope="function")
async def client(db_session, db_engine, sync_db_engine):
    # Override the get_db dependency to use our test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Patch the engine used in main.py's lifespan
    # AND patch the SessionLocal used by Celery tasks to use the sync test engine
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_db_engine)

    with patch("main.engine", db_engine), \
         patch("app.core.database.SessionLocal", TestSessionLocal), \
         patch("app.tasks.analysis.SessionLocal", TestSessionLocal):

        from httpx import ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()
