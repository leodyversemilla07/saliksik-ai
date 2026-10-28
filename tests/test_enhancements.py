"""Regression tests for the analysis / plagiarism / reviewer feature wiring.

Covers the defects found during the codebase review:

* manuscripts silently truncated to 10k characters,
* the Celery task receiving the whole manuscript instead of an id,
* the plagiarism threshold from the request/configuration being ignored,
* plagiarism comparisons leaking across tenants,
* reviewer suggestions triggering a lazy load in async context (MissingGreenlet),
* authors being assignable as reviewers of their own manuscript,
* invalid reviewer-assignment status transitions.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.analysis import ManuscriptAnalysis
from app.models.document_fingerprint import DocumentFingerprint
from app.models.reviewer import Reviewer, ReviewerMatch
from app.models.user import User

APP_ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, relative_path: str):
    """Load a source file as a standalone module (bypassing test mocks)."""
    spec = importlib.util.spec_from_file_location(module_name, APP_ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def real_plagiarism_service():
    """Load the plagiarism service with the real datasketch/xxhash/numpy."""
    mocked = {name: sys.modules.pop(name) for name in ("datasketch", "xxhash", "numpy") if name in sys.modules}
    try:
        yield _load_module("saliksik_real_plagiarism_detector", "app/services/plagiarism_detector.py")
    finally:
        for name, module in mocked.items():
            sys.modules[name] = module


@pytest.fixture(scope="module")
def real_reviewer_matcher():
    """Load the real reviewer matcher implementation."""
    return _load_module("saliksik_real_reviewer_matcher", "app/services/reviewer_matcher.py")


# ---------------------------------------------------------------------------
# Analysis submission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manuscript_above_limit_is_rejected(client, db_session):
    user = User(
        username="limituser",
        email="limit@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = await _login(client, "limituser")
    oversized = "word " * (settings.MAX_MANUSCRIPT_CHARS // 5 + 100)

    response = await client.post(
        "/api/v1/analysis/pre-review",
        data={"manuscript_text": oversized},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_submitted_manuscript_is_not_truncated(client, db_session):
    user = User(
        username="truncationuser",
        email="truncation@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = await _login(client, "truncationuser")
    manuscript = "alpha beta gamma delta epsilon " * 1000  # 30_000 characters

    with patch("app.tasks.analysis.process_manuscript_task.delay") as delay:
        delay.return_value = MagicMock(id="task-no-text")
        response = await client.post(
            "/api/v1/analysis/pre-review",
            data={"manuscript_text": manuscript},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 202

    stored = await db_session.execute(
        ManuscriptAnalysis.__table__.select().where(ManuscriptAnalysis.id == response.json()["analysis_id"])
    )
    assert stored is not None

    analysis = await db_session.get(ManuscriptAnalysis, response.json()["analysis_id"])
    assert analysis is not None
    assert len(analysis.manuscript_text) == len(manuscript.strip())
    assert len(analysis.manuscript_text) > 10_000


@pytest.mark.asyncio
async def test_celery_task_receives_only_the_analysis_id(client, db_session):
    user = User(
        username="queueuser",
        email="queue@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = await _login(client, "queueuser")

    with patch("app.tasks.analysis.process_manuscript_task.delay") as delay:
        delay.return_value = MagicMock(id="task-id-only")
        response = await client.post(
            "/api/v1/analysis/pre-review",
            data={"manuscript_text": "This is a valid manuscript body used for the regression test."},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 202
    delay.assert_called_once_with(response.json()["analysis_id"])
    args, _kwargs = delay.call_args
    assert len(args) == 1
    assert isinstance(args[0], int)


@pytest.mark.asyncio
async def test_analysis_status_includes_enhancement_results(client, db_session):
    user = User(
        username="enhancementuser",
        email="enhancement@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = await _login(client, "enhancementuser")

    analysis = ManuscriptAnalysis(
        user_id=user.id,
        original_filename="paper.pdf",
        input_type="pdf",
        manuscript_text="Manuscript body",
        status="COMPLETED",
        summary="A summary",
        keywords=["keyword"],
        language_quality={
            "word_count": 100,
            "unique_words": 80,
            "sentence_count": 5,
            "named_entities": 2,
            "readability_score": 55.0,
        },
        language_info={"code": "en", "name": "English", "confidence": 0.99},
        plagiarism_result={
            "is_plagiarized": False,
            "overall_similarity": 0.1,
            "similar_documents": [],
            "unique_content_percentage": 90.0,
            "processing_time": 0.2,
            "checked_against": 3,
        },
        citation_analysis={
            "total_citations": 2,
            "valid_citations": 2,
            "format_detected": "apa",
            "format_consistency": 90.0,
            "self_citations": 0,
            "average_citation_age": 4.5,
            "oldest_citation_year": 2018,
            "newest_citation_year": 2024,
            "missing_in_text": [],
            "orphan_citations": [],
            "issues": [],
        },
        task_id="task-enhanced",
    )
    db_session.add(analysis)
    await db_session.commit()

    response = await client.get(
        "/api/v1/analysis/status/task-enhanced",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"]["code"] == "en"
    assert payload["plagiarism"]["checked_against"] == 3
    assert payload["citation_analysis"]["total_citations"] == 2


# ---------------------------------------------------------------------------
# Plagiarism
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plagiarism_request_threshold_is_forwarded(client, db_session):
    user = User(
        username="plaguser",
        email="plag@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = await _login(client, "plaguser")

    detector = MagicMock()
    detector.check_similarity_with_database_async = AsyncMock(
        return_value=MagicMock(
            is_plagiarized=False,
            overall_similarity=0.0,
            similar_documents=[],
            unique_content_percentage=100.0,
            processing_time=0.01,
            checked_against=0,
        )
    )

    with patch("app.api.v1.plagiarism.get_plagiarism_detector", return_value=detector):
        response = await client.post(
            "/api/v1/plagiarism/check",
            json={"manuscript_text": "A manuscript body that is long enough to be checked.", "threshold": 0.42},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    kwargs = detector.check_similarity_with_database_async.await_args.kwargs
    assert kwargs["threshold"] == 0.42
    assert kwargs["user_id"] == user.id


def test_detector_uses_configured_threshold(real_plagiarism_service):
    detector = real_plagiarism_service.get_plagiarism_detector()

    assert detector.threshold == settings.PLAGIARISM_THRESHOLD


def test_similarity_respects_the_requested_threshold(real_plagiarism_service):
    detector = real_plagiarism_service.PlagiarismDetector(threshold=0.5)
    text = "machine learning improves predictive accuracy for scientific research papers"

    assert detector.add_to_index(1, text, "paper.pdf") is True

    baseline = detector.check_similarity(text)
    similarity = baseline.overall_similarity
    assert baseline.checked_against == 1

    strict = detector.check_similarity(text, threshold=similarity + 0.01)
    assert strict.is_plagiarized is False
    assert strict.checked_against == 1

    exact = detector.check_similarity(text, threshold=similarity)
    assert exact.is_plagiarized is True
    assert exact.similar_documents[0].analysis_id == 1


def test_unrelated_documents_are_not_flagged(real_plagiarism_service):
    detector = real_plagiarism_service.PlagiarismDetector(threshold=0.5)
    indexed = "machine learning improves predictive accuracy for scientific research papers"
    unrelated = "coastal erosion threatens historic harbour towns during severe winter storms"

    assert detector.add_to_index(1, indexed, "paper.pdf") is True

    result = detector.check_similarity(unrelated, threshold=0.1)

    assert result.is_plagiarized is False
    assert result.similar_documents == []


@pytest.mark.asyncio
async def test_database_comparison_is_scoped_to_the_tenant(real_plagiarism_service, db_session):
    detector = real_plagiarism_service.PlagiarismDetector(threshold=0.5)

    owner = User(
        username="tenantowner",
        email="tenantowner@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    other = User(
        username="tenantother",
        email="tenantother@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add_all([owner, other])
    await db_session.commit()

    text = "shared manuscript content about distributed database consensus protocols"

    owner_analysis = ManuscriptAnalysis(
        user_id=owner.id,
        input_type="text",
        manuscript_text=text,
        status="COMPLETED",
        summary="summary",
        keywords=[],
        language_quality={},
    )
    other_analysis = ManuscriptAnalysis(
        user_id=other.id,
        input_type="text",
        manuscript_text=text,
        status="COMPLETED",
        summary="summary",
        keywords=[],
        language_quality={},
    )
    db_session.add_all([owner_analysis, other_analysis])
    await db_session.commit()

    for analysis in (owner_analysis, other_analysis):
        fingerprint = detector.create_fingerprint_data(text)
        assert fingerprint is not None
        db_session.add(
            DocumentFingerprint(
                analysis_id=analysis.id,
                fingerprint_hash=fingerprint.fingerprint_hash,
                shingles=fingerprint.shingles,
            )
        )
    await db_session.commit()

    result = await detector.check_similarity_with_database_async(
        text=text,
        db=db_session,
        user_id=owner.id,
        threshold=0.5,
    )

    assert result.checked_against == 1
    assert [doc.analysis_id for doc in result.similar_documents] == [owner_analysis.id]
    assert result.is_plagiarized is True


# ---------------------------------------------------------------------------
# Reviewer matching / assignments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reviewer_suggestions_do_not_trigger_lazy_loads(real_reviewer_matcher, db_engine):
    """Reviewer.user must be eager loaded; otherwise async lazy loads raise MissingGreenlet."""
    maker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async with maker() as writer:
        reviewer_user = User(
            username="reviewermatcher",
            email="reviewermatcher@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            is_email_verified=True,
        )
        writer.add(reviewer_user)
        await writer.commit()
        writer.add(
            Reviewer(
                user_id=reviewer_user.id,
                expertise_keywords=["machine", "learning"],
                institution="Example University",
                is_available=True,
                current_assignments=0,
                max_assignments=5,
            )
        )
        await writer.commit()

    matcher = real_reviewer_matcher.ReviewerMatcher()
    real_reviewer_matcher.SENTENCE_TRANSFORMERS_AVAILABLE = False

    async with maker() as reader:
        suggestions = await matcher.find_matching_reviewers_async(
            manuscript_keywords=["machine", "learning"],
            manuscript_text="A manuscript about machine learning.",
            db=reader,
            top_n=5,
            min_score=0.1,
        )

    assert suggestions
    assert suggestions[0].username == "reviewermatcher"
    assert suggestions[0].match_method == "keyword"


@pytest.mark.asyncio
async def test_author_cannot_be_assigned_as_own_reviewer(client, db_session):
    user = User(
        username="selfassignuser",
        email="selfassign@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    reviewer = Reviewer(
        user_id=user.id,
        expertise_keywords=["science"],
        is_available=True,
        current_assignments=0,
        max_assignments=5,
    )
    analysis = ManuscriptAnalysis(
        user_id=user.id,
        input_type="text",
        manuscript_text="body",
        status="COMPLETED",
        summary="summary",
        keywords=["science"],
        language_quality={},
    )
    db_session.add_all([reviewer, analysis])
    await db_session.commit()

    token = await _login(client, "selfassignuser")

    response = await client.post(
        f"/api/v1/reviewers/analysis/{analysis.id}/assign/{reviewer.id}",
        json={"send_invitation": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "author" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_assignment_status_transitions_are_enforced(client, db_session):
    reviewer_user = User(
        username="transitionreviewer",
        email="transition@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    author = User(
        username="transitionauthor",
        email="transitionauthor@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_email_verified=True,
    )
    db_session.add_all([reviewer_user, author])
    await db_session.commit()

    reviewer = Reviewer(
        user_id=reviewer_user.id,
        expertise_keywords=["science"],
        is_available=True,
        current_assignments=1,
        max_assignments=5,
    )
    analysis = ManuscriptAnalysis(
        user_id=author.id,
        input_type="text",
        manuscript_text="body",
        status="COMPLETED",
        summary="summary",
        keywords=["science"],
        language_quality={},
    )
    db_session.add_all([reviewer, analysis])
    await db_session.commit()

    match = ReviewerMatch(
        analysis_id=analysis.id,
        reviewer_id=reviewer.id,
        match_score=0.8,
        matched_keywords=["science"],
        match_method="keyword",
        status="invited",
    )
    db_session.add(match)
    await db_session.commit()

    token = await _login(client, "transitionreviewer")

    invalid = await client.put(
        f"/api/v1/reviewers/assignments/{match.id}/status",
        json={"status": "suggested"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert invalid.status_code == 400

    accepted = await client.put(
        f"/api/v1/reviewers/assignments/{match.id}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    repeated = await client.put(
        f"/api/v1/reviewers/assignments/{match.id}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert repeated.status_code == 400


def test_orcid_format_is_validated():
    from pydantic import ValidationError

    from app.schemas.reviewer import ReviewerCreate

    valid = ReviewerCreate(
        expertise_keywords=["science"],
        orcid_id="0000-0002-1825-0097",
    )
    assert valid.orcid_id == "0000-0002-1825-0097"

    with pytest.raises(ValidationError):
        ReviewerCreate(expertise_keywords=["science"], orcid_id="not-an-orcid")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _login(client, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
