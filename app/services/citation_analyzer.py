"""
Citation analysis service for parsing and validating references.
Supports APA, MLA, IEEE, and Chicago citation formats.
"""
import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Represents a parsed citation/reference."""
    raw_text: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    title: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    format_valid: bool = True
    issues: List[str] = field(default_factory=list)
    line_number: Optional[int] = None


@dataclass
class InTextCitation:
    """Represents an in-text citation found in the manuscript."""
    raw_text: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    page: Optional[str] = None
    position: int = 0  # Character position in text


@dataclass
class CitationIssue:
    """Represents an issue found during citation validation."""
    issue_type: str  # format, missing, orphan, outdated
    description: str
    citation_text: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class CitationAnalysisResult:
    """Complete result of citation analysis."""
    total_citations: int
    valid_citations: int
    format_detected: str
    format_consistency: float  # Percentage of citations matching detected format
    self_citations: int
    average_citation_age: float
    oldest_citation_year: Optional[int]
    newest_citation_year: Optional[int]
    missing_in_text: List[str]  # References not cited in text
    orphan_citations: List[str]  # In-text citations without reference
    issues: List[CitationIssue] = field(default_factory=list)
    references: List[Citation] = field(default_factory=list)


class CitationAnalyzer:
    """
    Analyzer for parsing and validating academic citations.
    
    Supports detection and parsing of:
    - APA (American Psychological Association)
    - MLA (Modern Language Association)
    - IEEE (Institute of Electrical and Electronics Engineers)
    - Chicago style citations
    """
    
    SUPPORTED_FORMATS = ['apa', 'mla', 'ieee', 'chicago', 'unknown']
    
    # Regex patterns for different citation formats
    PATTERNS = {
        # APA: Author, A. A., & Author, B. B. (Year). Title. Journal, Volume(Issue), Pages.
        'apa': {
            'reference': re.compile(
                r'^([A-Z][a-zà-ÿ\-\']+(?:,\s*[A-Z]\.(?:\s*[A-Z]\.)*)?'
                r'(?:,?\s*(?:&|and)\s*[A-Z][a-zà-ÿ\-\']+(?:,\s*[A-Z]\.(?:\s*[A-Z]\.)*)?)*)'
                r'\s*\((\d{4}[a-z]?)\)\.'
                r'\s*(.+?)(?:\.|$)',
                re.MULTILINE | re.IGNORECASE
            ),
            'in_text': re.compile(
                r'\(([A-Z][a-zà-ÿ\-\']+(?:\s*(?:&|and|et\s+al\.?)\s*[A-Z][a-zà-ÿ\-\']+)?'
                r'(?:\s*et\s+al\.?)?),?\s*(\d{4}[a-z]?)(?:,\s*p\.?\s*\d+(?:-\d+)?)?\)',
                re.IGNORECASE
            )
        },
        # MLA: Author. "Title." Journal, vol. X, no. X, Year, pp. X-X.
        'mla': {
            'reference': re.compile(
                r'^([A-Z][a-zà-ÿ\-\']+(?:,\s*[A-Z][a-zà-ÿ\-\']+)?'
                r'(?:,?\s*(?:and)\s*[A-Z][a-zà-ÿ\-\']+(?:,\s*[A-Z][a-zà-ÿ\-\']+)?)*)\.'
                r'\s*["\"](.+?)["\"]',
                re.MULTILINE | re.IGNORECASE
            ),
            'in_text': re.compile(
                r'\(([A-Z][a-zà-ÿ\-\']+(?:\s+(?:and|et\s+al\.?)\s+[A-Z][a-zà-ÿ\-\']+)?)'
                r'\s+(\d+(?:-\d+)?)\)',
                re.IGNORECASE
            )
        },
        # IEEE: [1] A. Author, "Title," Journal, vol. X, no. X, pp. X-X, Year.
        'ieee': {
            'reference': re.compile(
                r'^\[(\d+)\]\s*([A-Z]\.(?:\s*[A-Z]\.)*\s*[A-Z][a-zà-ÿ\-\']+(?:,?\s*(?:and)?\s*[A-Z]\.(?:\s*[A-Z]\.)*\s*[A-Z][a-zà-ÿ\-\']+)*)'
                r',\s*["\"](.+?)["\"]',
                re.MULTILINE | re.IGNORECASE
            ),
            'in_text': re.compile(r'\[(\d+(?:\s*,\s*\d+)*(?:\s*-\s*\d+)?)\]')
        },
        # Chicago: Author. Title. Place: Publisher, Year.
        'chicago': {
            'reference': re.compile(
                r'^([A-Z][a-zà-ÿ\-\']+(?:,\s*[A-Z][a-zà-ÿ\-\']+)?)\.'
                r'\s*(.+?)\.'
                r'\s*(?:[A-Z][a-zà-ÿ\-\']+:\s*)?'
                r'(?:[A-Z][a-zà-ÿ\-\']+\s*(?:Press|Publishing|Books)?),?\s*(\d{4})',
                re.MULTILINE | re.IGNORECASE
            ),
            'in_text': re.compile(
                r'\(([A-Z][a-zà-ÿ\-\']+)\s+(\d{4}),?\s*(?:\d+(?:-\d+)?)?\)',
                re.IGNORECASE
            )
        }
    }
    
    # DOI pattern
    DOI_PATTERN = re.compile(r'(?:doi:?\s*|https?://doi\.org/)?(10\.\d{4,}/[^\s]+)', re.IGNORECASE)
    
    # Year pattern
    YEAR_PATTERN = re.compile(r'\b(19\d{2}|20\d{2})\b')
    
    def __init__(self, current_year: Optional[int] = None):
        """Initialize the citation analyzer."""
        self.current_year = current_year or datetime.now().year
        logger.info("CitationAnalyzer initialized")
    
    def _find_reference_section(self, text: str) -> Tuple[str, int]:
        """
        Find and extract the references section from the document.
        
        Returns:
            Tuple of (references_text, start_line_number)
        """
        # Common reference section headers
        headers = [
            r'\n\s*references?\s*\n',
            r'\n\s*bibliography\s*\n',
            r'\n\s*works?\s+cited\s*\n',
            r'\n\s*literature\s+cited\s*\n',
            r'\n\s*sources?\s*\n',
        ]
        
        for pattern in headers:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_pos = match.end()
                # Calculate line number
                line_number = text[:start_pos].count('\n') + 1
                return text[start_pos:], line_number
        
        # If no header found, try to find references at the end
        # Look for a section that starts with numbered citations or author names
        return text, 1
    
    def detect_format(self, text: str) -> str:
        """
        Detect the citation format used in the document.
        
        Returns:
            Format name ('apa', 'mla', 'ieee', 'chicago', or 'unknown')
        """
        scores = {fmt: 0 for fmt in self.SUPPORTED_FORMATS if fmt != 'unknown'}
        
        references_text, _ = self._find_reference_section(text)
        
        # Check for IEEE style (numbered references)
        ieee_refs = re.findall(r'^\s*\[\d+\]', references_text, re.MULTILINE)
        if ieee_refs:
            scores['ieee'] = len(ieee_refs) * 2
        
        # Check for APA style (Year in parentheses after author)
        apa_refs = re.findall(r'[A-Z][a-z]+,?\s+[A-Z]\.\s*\(\d{4}\)', references_text)
        scores['apa'] = len(apa_refs)
        
        # Check for MLA style (Titles in quotes)
        mla_refs = re.findall(r'[A-Z][a-z]+\.\s*[""].+?[""]', references_text)
        scores['mla'] = len(mla_refs)
        
        # Check for Chicago style (Titles in italics or specific patterns)
        chicago_refs = re.findall(r'[A-Z][a-z]+\.\s+[A-Z].+?\.\s+[A-Z][a-z]+:', references_text)
        scores['chicago'] = len(chicago_refs)
        
        # Return format with highest score
        max_score = max(scores.values())
        if max_score == 0:
            return 'unknown'
        
        for fmt, score in scores.items():
            if score == max_score:
                return fmt
        
        return 'unknown'
    
    def extract_references(self, text: str) -> List[Citation]:
        """
        Extract all references from the document.
        
        Returns:
            List of Citation objects
        """
        references = []
        references_text, start_line = self._find_reference_section(text)
        
        # Split by newlines and filter empty lines
        lines = [line.strip() for line in references_text.split('\n') if line.strip()]
        
        current_ref = ""
        ref_start_line = start_line
        
        for i, line in enumerate(lines):
            # Check if this is a new reference (starts with author name or number)
            is_new_ref = (
                re.match(r'^[A-Z][a-zà-ÿ\-\']+,', line) or  # Author, First
                re.match(r'^\[\d+\]', line) or  # [1] IEEE
                re.match(r'^\d+\.', line)  # 1. Numbered
            )
            
            if is_new_ref and current_ref:
                # Parse the completed reference
                citation = self._parse_reference(current_ref, ref_start_line)
                if citation:
                    references.append(citation)
                current_ref = line
                ref_start_line = start_line + i
            else:
                # Continue current reference
                current_ref += " " + line if current_ref else line
        
        # Don't forget the last reference
        if current_ref:
            citation = self._parse_reference(current_ref, ref_start_line)
            if citation:
                references.append(citation)
        
        return references
    
    def _parse_reference(self, ref_text: str, line_number: int) -> Optional[Citation]:
        """Parse a single reference string into a Citation object."""
        citation = Citation(
            raw_text=ref_text.strip(),
            line_number=line_number
        )
        
        # Extract DOI
        doi_match = self.DOI_PATTERN.search(ref_text)
        if doi_match:
            citation.doi = doi_match.group(1)
        
        # Extract year
        years = self.YEAR_PATTERN.findall(ref_text)
        if years:
            citation.year = int(years[0])
        
        # Extract authors (simplified: first comma-separated segment)
        author_match = re.match(r'^([A-Z][^.]+?)(?:\.|,\s*\()', ref_text)
        if author_match:
            author_str = author_match.group(1)
            # Split by 'and' or '&'
            authors = re.split(r'\s*(?:,\s*(?:and|&)\s*|,\s*&\s*|\s+and\s+|\s+&\s+)', author_str)
            citation.authors = [a.strip() for a in authors if a.strip()]
        
        # Check for common issues
        if not citation.year:
            citation.issues.append("Missing publication year")
            citation.format_valid = False
        if not citation.authors:
            citation.issues.append("Could not parse authors")
            citation.format_valid = False
        
        return citation
    
    def extract_in_text_citations(self, text: str) -> List[InTextCitation]:
        """
        Extract all in-text citations from the document body.
        
        Returns:
            List of InTextCitation objects
        """
        citations = []
        
        # Find reference section to exclude it
        ref_section, _ = self._find_reference_section(text)
        body_text = text.replace(ref_section, '') if ref_section != text else text
        
        # Try all format patterns
        for fmt in ['apa', 'mla', 'ieee', 'chicago']:
            pattern = self.PATTERNS[fmt]['in_text']
            for match in pattern.finditer(body_text):
                citation = InTextCitation(
                    raw_text=match.group(0),
                    position=match.start()
                )
                
                if fmt == 'ieee':
                    # IEEE uses numbers
                    pass
                else:
                    # Other formats have author and year
                    if match.lastindex >= 1:
                        citation.authors = [match.group(1)]
                    if match.lastindex >= 2:
                        try:
                            citation.year = int(match.group(2))
                        except ValueError:
                            pass
                
                citations.append(citation)
        
        return citations
    
    def validate_citations(
        self,
        references: List[Citation],
        in_text: List[InTextCitation]
    ) -> Tuple[List[str], List[str], List[CitationIssue]]:
        """
        Cross-validate references against in-text citations.
        
        Returns:
            Tuple of (missing_in_text, orphan_citations, issues)
        """
        issues = []
        
        # Build lookup sets
        ref_keys = set()
        for ref in references:
            if ref.authors and ref.year:
                key = f"{ref.authors[0].split(',')[0].split()[-1]}{ref.year}"
                ref_keys.add(key.lower())
        
        intext_keys = set()
        for cite in in_text:
            if cite.authors and cite.year:
                key = f"{cite.authors[0].split()[-1]}{cite.year}"
                intext_keys.add(key.lower())
        
        # Find missing and orphans
        missing_in_text = ref_keys - intext_keys
        orphan_citations = intext_keys - ref_keys
        
        for missing in missing_in_text:
            issues.append(CitationIssue(
                issue_type="missing",
                description=f"Reference '{missing}' not cited in text"
            ))
        
        for orphan in orphan_citations:
            issues.append(CitationIssue(
                issue_type="orphan",
                description=f"In-text citation '{orphan}' has no matching reference"
            ))
        
        return list(missing_in_text), list(orphan_citations), issues
    
    def analyze(self, text: str) -> CitationAnalysisResult:
        """
        Perform complete citation analysis on a manuscript.
        
        Returns:
            CitationAnalysisResult with all findings
        """
        # Detect format
        detected_format = self.detect_format(text)
        
        # Extract references and in-text citations
        references = self.extract_references(text)
        in_text_citations = self.extract_in_text_citations(text)
        
        # Validate
        missing, orphans, validation_issues = self.validate_citations(
            references, in_text_citations
        )
        
        # Calculate statistics
        valid_count = sum(1 for r in references if r.format_valid)
        years = [r.year for r in references if r.year]
        
        # Check for outdated references (older than 10 years)
        outdated_threshold = self.current_year - 10
        for ref in references:
            if ref.year and ref.year < outdated_threshold:
                ref.issues.append(f"Citation is over 10 years old ({ref.year})")
                validation_issues.append(CitationIssue(
                    issue_type="outdated",
                    description=f"Reference from {ref.year} is over 10 years old",
                    citation_text=ref.raw_text[:100],
                    line_number=ref.line_number
                ))
        
        # Collect all issues
        all_issues = validation_issues.copy()
        for ref in references:
            for issue in ref.issues:
                if "over 10 years old" not in issue:  # Avoid duplicates
                    all_issues.append(CitationIssue(
                        issue_type="format",
                        description=issue,
                        citation_text=ref.raw_text[:100],
                        line_number=ref.line_number
                    ))
        
        # Calculate format consistency
        format_consistency = (valid_count / len(references) * 100) if references else 100.0
        
        # Calculate average age
        avg_age = (
            sum(self.current_year - y for y in years) / len(years)
            if years else 0.0
        )
        
        return CitationAnalysisResult(
            total_citations=len(references),
            valid_citations=valid_count,
            format_detected=detected_format,
            format_consistency=round(format_consistency, 2),
            self_citations=0,  # Would need author info to detect
            average_citation_age=round(avg_age, 2),
            oldest_citation_year=min(years) if years else None,
            newest_citation_year=max(years) if years else None,
            missing_in_text=missing,
            orphan_citations=orphans,
            issues=all_issues,
            references=references
        )


# Singleton instance
_citation_analyzer: Optional[CitationAnalyzer] = None


def get_citation_analyzer() -> CitationAnalyzer:
    """Get or create the singleton CitationAnalyzer instance."""
    global _citation_analyzer
    if _citation_analyzer is None:
        _citation_analyzer = CitationAnalyzer()
    return _citation_analyzer
