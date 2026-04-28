"""
Pydantic schemas for plagiarism detection.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SimilarDocument(BaseModel):
    """A document found to be similar during plagiarism check."""

    analysis_id: int = Field(..., description="ID of the similar manuscript analysis")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score (0.0-1.0)"
    )
    matched_segments: List[str] = Field(
        default_factory=list, description="Sample text segments that matched"
    )
    original_filename: Optional[str] = Field(
        None, description="Original filename of the similar document"
    )

    model_config = ConfigDict(from_attributes=True)


class PlagiarismResult(BaseModel):
    """Result of a plagiarism detection analysis."""

    is_plagiarized: bool = Field(
        ..., description="True if similarity exceeds threshold"
    )
    overall_similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Highest similarity score found (0.0-1.0)"
    )
    similar_documents: List[SimilarDocument] = Field(
        default_factory=list, description="List of similar documents found"
    )
    unique_content_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of content considered unique"
    )
    processing_time: float = Field(
        ..., description="Time taken for plagiarism check in seconds"
    )
    checked_against: int = Field(
        default=0, description="Number of documents compared against"
    )

    model_config = ConfigDict(from_attributes=True)


class PlagiarismCheckRequest(BaseModel):
    """Request schema for plagiarism check endpoint."""

    manuscript_text: str = Field(
        ...,
        min_length=50,
        max_length=100000,
        description="Manuscript text to check for plagiarism",
    )
    threshold: Optional[float] = Field(
        default=0.5, ge=0.1, le=0.95, description="Similarity threshold (0.1-0.95)"
    )


class PlagiarismIndexStats(BaseModel):
    """Statistics about the plagiarism detection index."""

    documents_indexed: int = Field(..., description="Number of documents in the index")
    threshold: float = Field(..., description="Default similarity threshold")
    num_permutations: int = Field(..., description="MinHash permutation count")
    shingle_size: int = Field(..., description="N-gram size for shingling")
    datasketch_available: bool = Field(
        ..., description="Whether datasketch library is available"
    )
    xxhash_available: bool = Field(
        ..., description="Whether xxhash library is available"
    )
