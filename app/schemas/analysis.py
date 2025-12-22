"""
Analysis schemas for manuscript processing.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.schemas.plagiarism import PlagiarismResult
from app.schemas.citation import CitationAnalysisResult


class AnalysisRequest(BaseModel):
    """Analysis request schema."""
    manuscript_text: str = Field(..., min_length=50, max_length=250000)  # Approx 40k words


class DemoAnalysisRequest(BaseModel):
    """Demo analysis request schema (limited)."""
    manuscript_text: str = Field(..., min_length=50, max_length=5000)


class LanguageQuality(BaseModel):
    """Language quality metrics."""
    word_count: int
    unique_words: int
    sentence_count: int
    named_entities: int
    readability_score: float
    grammar_issues: Optional[int] = None
    grammar_check_available: Optional[bool] = None


class LanguageInfo(BaseModel):
    """Detected language information."""
    code: str = Field(..., description="ISO 639-1 language code (e.g., 'en', 'es')")
    name: str = Field(..., description="Full language name (e.g., 'English')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")


class AnalysisMetadata(BaseModel):
    """Analysis metadata."""
    analysis_id: Optional[int] = None
    input_length: int
    processing_time: float
    user: Optional[str] = None
    timestamp: Optional[datetime] = None
    cached: bool = False
    demo: bool = False


class AnalysisResponse(BaseModel):
    """Analysis response schema."""
    summary: str
    keywords: List[str]
    language_quality: LanguageQuality
    metadata: AnalysisMetadata
    # Enhancement features (all optional)
    language: Optional[LanguageInfo] = None  # Phase 4: Multi-language
    plagiarism: Optional[PlagiarismResult] = None  # Phase 1: Plagiarism detection
    citation_analysis: Optional[CitationAnalysisResult] = None  # Phase 2: Citation analysis


class AnalysisHistoryItem(BaseModel):
    """Single analysis history item."""
    id: int
    filename: Optional[str]
    input_type: str
    word_count: int
    readability_score: float
    created_at: datetime
    processing_time: Optional[float]
    
    class Config:
        from_attributes = True


class AnalysisHistoryResponse(BaseModel):
    """Paginated analysis history response."""
    results: List[AnalysisHistoryItem]
    pagination: Dict[str, Any]
