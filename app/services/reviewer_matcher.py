"""
Reviewer matching service using keyword and semantic similarity.
Matches manuscripts with reviewers based on expertise.
"""

import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ReviewerSuggestion:
    """A suggested reviewer match for a manuscript."""

    reviewer_id: int
    user_id: int
    username: str
    match_score: float
    matched_keywords: List[str]
    match_method: str  # keyword, semantic, hybrid
    institution: Optional[str] = None
    expertise_keywords: List[str] = None
    available_slots: int = 0


class ReviewerMatcher:
    """
    Service for matching manuscripts with appropriate reviewers.

    Uses a hybrid approach combining:
    1. Keyword matching (exact and stemmed)
    2. Semantic similarity (using sentence transformers)
    """

    MODEL_NAME = "all-MiniLM-L6-v2"  # Lightweight but effective model

    def __init__(self):
        """Initialize the reviewer matcher."""
        self._model = None
        logger.info("ReviewerMatcher initialized")

    @property
    def model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._model = SentenceTransformer(self.MODEL_NAME)
                logger.info(f"Loaded sentence transformer model: {self.MODEL_NAME}")
            except Exception as e:
                logger.error(f"Failed to load sentence transformer: {e}")
                self._model = None
        return self._model

    def create_expertise_embedding(
        self, keywords: List[str], description: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Create an embedding vector from reviewer expertise.

        Args:
            keywords: List of expertise keywords
            description: Optional expertise description

        Returns:
            Serialized embedding as bytes, or None if unavailable
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE or self.model is None:
            logger.warning("Sentence transformers not available for embedding creation")
            return None

        try:
            # Combine keywords and description into text
            text_parts = keywords.copy()
            if description:
                text_parts.append(description)

            combined_text = " ".join(text_parts)

            if not combined_text.strip():
                return None

            # Generate embedding
            embedding = self.model.encode(combined_text, convert_to_numpy=True)

            # Serialize as JSON (safe, no arbitrary code execution)
            return json.dumps(embedding.tolist()).encode("utf-8")

        except Exception as e:
            logger.error(f"Failed to create expertise embedding: {e}")
            return None

    def _deserialize_embedding(self, embedding_bytes: bytes) -> Optional[np.ndarray]:
        """Deserialize an embedding from JSON-encoded bytes."""
        try:
            return np.array(
                json.loads(embedding_bytes.decode("utf-8")), dtype=np.float64
            )
        except Exception as e:
            logger.error(f"Failed to deserialize embedding: {e}")
            return None

    def calculate_keyword_similarity(
        self, manuscript_keywords: List[str], reviewer_keywords: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate keyword-based similarity between manuscript and reviewer.

        Returns:
            Tuple of (similarity score, matched keywords)
        """
        if not manuscript_keywords or not reviewer_keywords:
            return 0.0, []

        # Normalize keywords to lowercase
        ms_keywords = set(k.lower().strip() for k in manuscript_keywords)
        rv_keywords = set(k.lower().strip() for k in reviewer_keywords)

        # Find exact matches
        matched = ms_keywords.intersection(rv_keywords)

        # Also check for partial matches (one keyword contains another)
        partial_matches = set()
        for ms_kw in ms_keywords:
            for rv_kw in rv_keywords:
                if ms_kw in rv_kw or rv_kw in ms_kw:
                    if ms_kw not in matched and rv_kw not in matched:
                        partial_matches.add(f"{ms_kw}~{rv_kw}")

        # Calculate Jaccard-like score
        total_keywords = len(ms_keywords.union(rv_keywords))
        match_count = len(matched) + (len(partial_matches) * 0.5)

        similarity = match_count / total_keywords if total_keywords > 0 else 0.0

        return min(similarity, 1.0), list(matched)

    def calculate_semantic_similarity(
        self, manuscript_text: str, reviewer_embedding: bytes
    ) -> float:
        """
        Calculate semantic similarity using embeddings.

        Returns:
            Similarity score between 0 and 1
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE or self.model is None:
            return 0.0

        try:
            # Generate manuscript embedding
            ms_embedding = self.model.encode(manuscript_text, convert_to_numpy=True)

            # Deserialize reviewer embedding
            rv_embedding = self._deserialize_embedding(reviewer_embedding)
            if rv_embedding is None:
                return 0.0

            # Calculate cosine similarity
            similarity = np.dot(ms_embedding, rv_embedding) / (
                np.linalg.norm(ms_embedding) * np.linalg.norm(rv_embedding)
            )

            # Convert from [-1, 1] to [0, 1]
            return float((similarity + 1) / 2)

        except Exception as e:
            logger.error(f"Semantic similarity calculation failed: {e}")
            return 0.0

    def calculate_hybrid_score(
        self, keyword_score: float, semantic_score: float, keyword_weight: float = 0.6
    ) -> float:
        """
        Combine keyword and semantic scores into a hybrid score.

        Args:
            keyword_score: Keyword matching score (0-1)
            semantic_score: Semantic similarity score (0-1)
            keyword_weight: Weight for keyword score (default 0.6)

        Returns:
            Combined score between 0 and 1
        """
        semantic_weight = 1 - keyword_weight
        return (keyword_score * keyword_weight) + (semantic_score * semantic_weight)

    async def find_matching_reviewers_async(
        self,
        manuscript_keywords: List[str],
        manuscript_text: str,
        db: AsyncSession,
        top_n: int = 5,
        min_score: float = 0.1,
        exclude_user_ids: Optional[List[int]] = None,
    ) -> List[ReviewerSuggestion]:
        """
        Find reviewers matching a manuscript based on expertise (async version).

        Args:
            manuscript_keywords: Keywords extracted from the manuscript
            manuscript_text: Full manuscript text (for semantic matching)
            db: Async database session
            top_n: Maximum number of suggestions to return
            min_score: Minimum match score to include
            exclude_user_ids: User IDs to exclude (e.g., manuscript author)

        Returns:
            List of ReviewerSuggestion sorted by match score
        """
        from app.models.reviewer import Reviewer

        exclude_user_ids = exclude_user_ids or []
        suggestions = []

        # Query available reviewers (async)
        stmt = select(Reviewer).filter(Reviewer.is_available)

        if exclude_user_ids:
            stmt = stmt.filter(Reviewer.user_id.notin_(exclude_user_ids))

        result = await db.execute(stmt)
        reviewers = result.scalars().all()

        for reviewer in reviewers:
            if not reviewer.is_accepting_reviews:
                continue

            # Calculate keyword similarity
            keyword_score, matched_keywords = self.calculate_keyword_similarity(
                manuscript_keywords, reviewer.expertise_keywords or []
            )

            # Calculate semantic similarity if embedding exists
            semantic_score = 0.0
            match_method = "keyword"

            if reviewer.expertise_embedding:
                # Use summary or first part of text for semantic matching
                text_sample = manuscript_text[:2000] if manuscript_text else ""
                semantic_score = self.calculate_semantic_similarity(
                    text_sample, reviewer.expertise_embedding
                )

                if semantic_score > 0:
                    match_method = "hybrid" if keyword_score > 0 else "semantic"

            # Calculate final score
            if match_method == "hybrid":
                final_score = self.calculate_hybrid_score(keyword_score, semantic_score)
            elif match_method == "semantic":
                final_score = semantic_score
            else:
                final_score = keyword_score

            # Only include if above threshold
            if final_score >= min_score:
                suggestions.append(
                    ReviewerSuggestion(
                        reviewer_id=reviewer.id,
                        user_id=reviewer.user_id,
                        username=reviewer.user.username if reviewer.user else "Unknown",
                        match_score=round(final_score, 4),
                        matched_keywords=matched_keywords,
                        match_method=match_method,
                        institution=reviewer.institution,
                        expertise_keywords=reviewer.expertise_keywords or [],
                        available_slots=reviewer.available_slots,
                    )
                )

        # Sort by match score descending
        suggestions.sort(key=lambda x: x.match_score, reverse=True)

        return suggestions[:top_n]

    def check_conflict_of_interest(
        self,
        manuscript_user_id: int,
        reviewer_user_id: int,
        manuscript_institution: Optional[str] = None,
        reviewer_institution: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Check for potential conflicts of interest.

        Returns:
            Tuple of (has_conflict, reasons)
        """
        conflicts = []

        # Same user
        if manuscript_user_id == reviewer_user_id:
            conflicts.append("Reviewer is the manuscript author")

        # Same institution (if provided)
        if manuscript_institution and reviewer_institution:
            if manuscript_institution.lower() == reviewer_institution.lower():
                conflicts.append("Reviewer is from the same institution as the author")

        return len(conflicts) > 0, conflicts


# Singleton instance
_reviewer_matcher: Optional[ReviewerMatcher] = None


def get_reviewer_matcher() -> ReviewerMatcher:
    """Get or create the singleton ReviewerMatcher instance."""
    global _reviewer_matcher
    if _reviewer_matcher is None:
        _reviewer_matcher = ReviewerMatcher()
    return _reviewer_matcher
