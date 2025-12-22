"""
Pydantic schemas for citation analysis.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Citation(BaseModel):
    """A parsed citation/reference from the manuscript."""
    raw_text: str = Field(..., description="Original citation text")
    authors: List[str] = Field(default_factory=list, description="List of author names")
    year: Optional[int] = Field(None, description="Publication year")
    title: Optional[str] = Field(None, description="Title of the work")
    journal: Optional[str] = Field(None, description="Journal or publication name")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    format_valid: bool = Field(True, description="Whether the citation format is valid")
    issues: List[str] = Field(default_factory=list, description="Format issues found")
    line_number: Optional[int] = Field(None, description="Line number in document")
    
    class Config:
        from_attributes = True


class InTextCitation(BaseModel):
    """An in-text citation found in the manuscript body."""
    raw_text: str = Field(..., description="The in-text citation as it appears")
    authors: List[str] = Field(default_factory=list, description="Author names referenced")
    year: Optional[int] = Field(None, description="Year referenced")
    page: Optional[str] = Field(None, description="Page number if specified")
    position: int = Field(0, description="Character position in text")
    
    class Config:
        from_attributes = True


class CitationIssue(BaseModel):
    """An issue found during citation validation."""
    issue_type: str = Field(
        ..., 
        description="Type of issue: format, missing, orphan, outdated"
    )
    description: str = Field(..., description="Description of the issue")
    citation_text: Optional[str] = Field(None, description="Relevant citation text")
    line_number: Optional[int] = Field(None, description="Line number if applicable")
    
    class Config:
        from_attributes = True


class CitationAnalysisResult(BaseModel):
    """Complete result of citation analysis."""
    total_citations: int = Field(..., description="Total number of references found")
    valid_citations: int = Field(..., description="Number of properly formatted citations")
    format_detected: str = Field(
        ..., 
        description="Detected citation format (apa, mla, ieee, chicago, unknown)"
    )
    format_consistency: float = Field(
        ..., 
        ge=0.0, 
        le=100.0,
        description="Percentage of citations matching detected format"
    )
    self_citations: int = Field(0, description="Number of self-citations detected")
    average_citation_age: float = Field(..., description="Average age of citations in years")
    oldest_citation_year: Optional[int] = Field(None, description="Year of oldest citation")
    newest_citation_year: Optional[int] = Field(None, description="Year of newest citation")
    missing_in_text: List[str] = Field(
        default_factory=list,
        description="References not cited in the text body"
    )
    orphan_citations: List[str] = Field(
        default_factory=list,
        description="In-text citations without matching references"
    )
    issues: List[CitationIssue] = Field(
        default_factory=list,
        description="All issues found during analysis"
    )
    
    class Config:
        from_attributes = True


class CitationAnalysisRequest(BaseModel):
    """Request schema for citation analysis endpoint."""
    manuscript_text: str = Field(
        ...,
        min_length=100,
        max_length=100000,
        description="Full manuscript text including references section"
    )
