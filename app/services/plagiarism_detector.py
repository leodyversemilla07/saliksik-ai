"""
Plagiarism detection service using MinHash LSH algorithm.
Provides similarity checking for manuscripts against stored documents.
"""

import hashlib
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import re

try:
    from datasketch import MinHash, MinHashLSH

    DATASKETCH_AVAILABLE = True
except ImportError:
    DATASKETCH_AVAILABLE = False

try:
    import xxhash

    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


@dataclass
class SimilarDocument:
    """Represents a similar document found during plagiarism check."""

    analysis_id: int
    similarity_score: float
    matched_segments: List[str]
    original_filename: Optional[str] = None


@dataclass
class PlagiarismResult:
    """Result of plagiarism detection analysis."""

    is_plagiarized: bool
    overall_similarity: float
    similar_documents: List[SimilarDocument]
    unique_content_percentage: float
    processing_time: float
    checked_against: int  # Number of documents compared


class PlagiarismDetector:
    """
    Plagiarism detection using MinHash Locality Sensitive Hashing (LSH).

    This algorithm works by:
    1. Breaking text into n-grams (shingles)
    2. Creating a MinHash signature for each document
    3. Using LSH to efficiently find similar documents
    """

    def __init__(
        self, num_perm: int = 128, threshold: float = 0.5, shingle_size: int = 5
    ):
        """
        Initialize the plagiarism detector.

        Args:
            num_perm: Number of permutations for MinHash (higher = more accurate but slower)
            threshold: Similarity threshold (0.0-1.0) for considering documents similar
            shingle_size: Size of n-grams (words) for shingling
        """
        self.num_perm = num_perm
        self.threshold = threshold
        self.shingle_size = shingle_size

        if not DATASKETCH_AVAILABLE:
            logger.warning(
                "datasketch not available. Plagiarism detection will be limited."
            )
            self._lsh = None
        else:
            self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)

        # In-memory index for documents (for demo/testing)
        self._document_index: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"PlagiarismDetector initialized (threshold={threshold}, shingles={shingle_size})"
        )

    def _preprocess_text(self, text: str) -> str:
        """Normalize and clean text for comparison."""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove punctuation except apostrophes
        text = re.sub(r"[^\w\s\']", "", text)
        return text.strip()

    def _create_shingles(self, text: str) -> set:
        """
        Create n-gram shingles from text.

        Args:
            text: Preprocessed text

        Returns:
            Set of word n-grams
        """
        words = text.split()
        if len(words) < self.shingle_size:
            # If text is too short, use individual words
            return set(words)

        shingles = set()
        for i in range(len(words) - self.shingle_size + 1):
            shingle = " ".join(words[i : i + self.shingle_size])
            shingles.add(shingle)

        return shingles

    def create_fingerprint(self, text: str) -> Optional[bytes]:
        """
        Create a MinHash fingerprint for a document.

        Args:
            text: Document text

        Returns:
            Serialized MinHash object as bytes, or None if unavailable
        """
        if not DATASKETCH_AVAILABLE:
            logger.warning("Cannot create fingerprint: datasketch not available")
            return None

        preprocessed = self._preprocess_text(text)
        shingles = self._create_shingles(preprocessed)

        minhash = MinHash(num_perm=self.num_perm)
        for shingle in shingles:
            if XXHASH_AVAILABLE:
                # Use xxhash for faster hashing
                minhash.update(xxhash.xxh64(shingle.encode("utf-8")).digest())
            else:
                minhash.update(shingle.encode("utf-8"))

        # Serialize MinHash hash values as JSON (safe, no arbitrary code execution)
        return json.dumps(minhash.hashvalues.tolist()).encode("utf-8")

    def _deserialize_fingerprint(self, fingerprint_bytes: bytes) -> Optional["MinHash"]:
        """Deserialize a MinHash fingerprint from JSON-encoded hash values."""
        try:
            import numpy as np

            hash_values = np.array(
                json.loads(fingerprint_bytes.decode("utf-8")), dtype=np.uint64
            )
            mh = MinHash(num_perm=len(hash_values))
            mh.hashvalues = hash_values
            return mh
        except Exception as e:
            logger.error(f"Failed to deserialize fingerprint: {e}")
            return None

    def add_to_index(
        self, doc_id: int, text: str, filename: Optional[str] = None
    ) -> bool:
        """
        Add a document to the LSH index for future comparisons.

        Args:
            doc_id: Unique document/analysis ID
            text: Document text
            filename: Optional original filename

        Returns:
            True if successfully added, False otherwise
        """
        if not DATASKETCH_AVAILABLE or self._lsh is None:
            logger.warning("Cannot add to index: datasketch not available")
            return False

        try:
            preprocessed = self._preprocess_text(text)
            shingles = self._create_shingles(preprocessed)

            minhash = MinHash(num_perm=self.num_perm)
            for shingle in shingles:
                if XXHASH_AVAILABLE:
                    minhash.update(xxhash.xxh64(shingle.encode("utf-8")).digest())
                else:
                    minhash.update(shingle.encode("utf-8"))

            key = f"doc_{doc_id}"

            # Store in LSH index
            self._lsh.insert(key, minhash)

            # Store metadata
            self._document_index[key] = {
                "analysis_id": doc_id,
                "filename": filename,
                "minhash": minhash,
                "shingles": shingles,
            }

            logger.info(f"Added document {doc_id} to plagiarism index")
            return True

        except Exception as e:
            logger.error(f"Failed to add document to index: {e}")
            return False

    def calculate_similarity(self, minhash1: "MinHash", minhash2: "MinHash") -> float:
        """Calculate Jaccard similarity between two MinHash objects."""
        return minhash1.jaccard(minhash2)

    def find_matching_segments(
        self, text1_shingles: set, text2_shingles: set, max_segments: int = 5
    ) -> List[str]:
        """Find overlapping text segments between two documents."""
        common = text1_shingles.intersection(text2_shingles)
        # Return up to max_segments examples
        return list(common)[:max_segments]

    def check_similarity(
        self,
        text: str,
        db=None,  # unused, kept for backward compat
        exclude_ids: Optional[List[int]] = None,
    ) -> PlagiarismResult:
        """
        Check a manuscript for similarity against indexed documents.

        Args:
            text: Manuscript text to check
            db: Optional database session to check against stored fingerprints
            exclude_ids: Document IDs to exclude from comparison

        Returns:
            PlagiarismResult with similarity findings
        """
        import time

        start_time = time.time()

        exclude_ids = exclude_ids or []
        similar_documents: List[SimilarDocument] = []

        if not DATASKETCH_AVAILABLE or self._lsh is None:
            logger.warning("Plagiarism check unavailable: datasketch not installed")
            return PlagiarismResult(
                is_plagiarized=False,
                overall_similarity=0.0,
                similar_documents=[],
                unique_content_percentage=100.0,
                processing_time=time.time() - start_time,
                checked_against=0,
            )

        # Create MinHash for input text
        preprocessed = self._preprocess_text(text)
        input_shingles = self._create_shingles(preprocessed)

        input_minhash = MinHash(num_perm=self.num_perm)
        for shingle in input_shingles:
            if XXHASH_AVAILABLE:
                input_minhash.update(xxhash.xxh64(shingle.encode("utf-8")).digest())
            else:
                input_minhash.update(shingle.encode("utf-8"))

        # Query LSH for candidates
        candidates = self._lsh.query(input_minhash)

        max_similarity = 0.0
        checked_count = 0

        for candidate_key in candidates:
            if candidate_key in self._document_index:
                doc_info = self._document_index[candidate_key]
                doc_id = doc_info["analysis_id"]

                # Skip excluded documents
                if doc_id in exclude_ids:
                    continue

                checked_count += 1
                doc_minhash = doc_info["minhash"]
                doc_shingles = doc_info["shingles"]

                # Calculate exact similarity
                similarity = self.calculate_similarity(input_minhash, doc_minhash)

                if similarity > self.threshold:
                    matched_segments = self.find_matching_segments(
                        input_shingles, doc_shingles
                    )

                    similar_documents.append(
                        SimilarDocument(
                            analysis_id=doc_id,
                            similarity_score=round(similarity, 4),
                            matched_segments=matched_segments,
                            original_filename=doc_info.get("filename"),
                        )
                    )

                    max_similarity = max(max_similarity, similarity)

        # Sort by similarity score descending
        similar_documents.sort(key=lambda x: x.similarity_score, reverse=True)

        processing_time = time.time() - start_time

        return PlagiarismResult(
            is_plagiarized=max_similarity >= self.threshold,
            overall_similarity=round(max_similarity, 4),
            similar_documents=similar_documents[:10],  # Top 10 matches
            unique_content_percentage=round((1 - max_similarity) * 100, 2),
            processing_time=round(processing_time, 3),
            checked_against=checked_count,
        )

    async def check_similarity_with_database_async(
        self, text: str, db: AsyncSession, exclude_id: Optional[int] = None
    ) -> PlagiarismResult:
        """
        Check similarity against documents stored in database (async version).

        Args:
            text: Manuscript text to check
            db: Async database session
            exclude_id: Analysis ID to exclude (e.g., the current document)

        Returns:
            PlagiarismResult with findings
        """
        import time
        from app.models.document_fingerprint import DocumentFingerprint

        start_time = time.time()
        similar_documents: List[SimilarDocument] = []

        if not DATASKETCH_AVAILABLE:
            return PlagiarismResult(
                is_plagiarized=False,
                overall_similarity=0.0,
                similar_documents=[],
                unique_content_percentage=100.0,
                processing_time=time.time() - start_time,
                checked_against=0,
            )

        # Create MinHash for input
        preprocessed = self._preprocess_text(text)
        input_shingles = self._create_shingles(preprocessed)

        input_minhash = MinHash(num_perm=self.num_perm)
        for shingle in input_shingles:
            if XXHASH_AVAILABLE:
                input_minhash.update(xxhash.xxh64(shingle.encode("utf-8")).digest())
            else:
                input_minhash.update(shingle.encode("utf-8"))

        # Query all fingerprints from database (async)
        stmt = select(DocumentFingerprint)
        if exclude_id:
            stmt = stmt.filter(DocumentFingerprint.analysis_id != exclude_id)

        result = await db.execute(stmt)
        fingerprints = result.scalars().all()
        max_similarity = 0.0

        for fp in fingerprints:
            stored_minhash = self._deserialize_fingerprint(fp.fingerprint_hash)
            if stored_minhash is None:
                continue

            similarity = self.calculate_similarity(input_minhash, stored_minhash)

            if similarity > self.threshold:
                # Get shingles for segment matching
                stored_shingles = set(fp.shingles) if fp.shingles else set()
                matched_segments = self.find_matching_segments(
                    input_shingles, stored_shingles
                )

                # Get filename from related analysis
                filename = None
                if fp.analysis and fp.analysis.original_filename:
                    filename = fp.analysis.original_filename

                similar_documents.append(
                    SimilarDocument(
                        analysis_id=fp.analysis_id,
                        similarity_score=round(similarity, 4),
                        matched_segments=matched_segments,
                        original_filename=filename,
                    )
                )

                max_similarity = max(max_similarity, similarity)

        similar_documents.sort(key=lambda x: x.similarity_score, reverse=True)

        return PlagiarismResult(
            is_plagiarized=max_similarity >= self.threshold,
            overall_similarity=round(max_similarity, 4),
            similar_documents=similar_documents[:10],
            unique_content_percentage=round((1 - max_similarity) * 100, 2),
            processing_time=round(time.time() - start_time, 3),
            checked_against=len(fingerprints),
        )

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current index."""
        return {
            "documents_indexed": len(self._document_index),
            "threshold": self.threshold,
            "num_permutations": self.num_perm,
            "shingle_size": self.shingle_size,
            "datasketch_available": DATASKETCH_AVAILABLE,
            "xxhash_available": XXHASH_AVAILABLE,
        }


# Singleton instance for the application
_plagiarism_detector: Optional[PlagiarismDetector] = None


def get_plagiarism_detector() -> PlagiarismDetector:
    """Get or create the singleton PlagiarismDetector instance."""
    global _plagiarism_detector
    if _plagiarism_detector is None:
        _plagiarism_detector = PlagiarismDetector()
    return _plagiarism_detector
