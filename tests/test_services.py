"""
Tests for service layer components.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestCitationAnalyzer:
    """Tests for CitationAnalyzer service."""
    
    def test_detect_apa_format(self):
        """Test APA format detection."""
        from app.services.citation_analyzer import CitationAnalyzer
        
        analyzer = CitationAnalyzer()
        
        apa_text = """
        References
        
        Smith, J. A. (2020). A study of something important. Journal of Science, 10(2), 123-145.
        Johnson, B. C., & Williams, D. E. (2019). Another important study. Research Quarterly, 5(1), 50-75.
        """
        
        detected = analyzer.detect_format(apa_text)
        assert detected == 'apa'
    
    def test_detect_ieee_format(self):
        """Test IEEE format detection."""
        from app.services.citation_analyzer import CitationAnalyzer
        
        analyzer = CitationAnalyzer()
        
        ieee_text = """
        References
        
        [1] J. A. Smith, "A study of something important," Journal of Science, vol. 10, no. 2, pp. 123-145, 2020.
        [2] B. C. Johnson and D. E. Williams, "Another study," Research Quarterly, vol. 5, no. 1, pp. 50-75, 2019.
        """
        
        detected = analyzer.detect_format(ieee_text)
        assert detected == 'ieee'
    
    def test_extract_year(self):
        """Test year extraction from citations."""
        from app.services.citation_analyzer import CitationAnalyzer
        
        analyzer = CitationAnalyzer()
        
        text = """
        References
        
        Smith, J. (2020). A test study. Test Journal.
        Johnson, B. (2015). Another test. Science Journal.
        """
        
        result = analyzer.analyze(text)
        years = [ref.year for ref in result.references if ref.year]
        
        assert 2020 in years or 2015 in years


class TestLanguageDetector:
    """Tests for LanguageDetector service."""
    
    def test_detect_english(self):
        """Test English language detection."""
        from app.services.language_detector import LanguageDetector
        
        detector = LanguageDetector()
        
        english_text = "This is a sample text in English for testing the language detection functionality."
        
        result = detector.detect_language(english_text)
        
        assert result.code == 'en'
        assert result.name == 'English'
        assert result.confidence > 0
    
    def test_short_text_defaults(self):
        """Test that short text returns default language."""
        from app.services.language_detector import LanguageDetector
        
        detector = LanguageDetector(default_language='en')
        
        result = detector.detect_language("Short")
        
        assert result.code == 'en'
        assert result.confidence == 1.0
    
    def test_supported_languages(self):
        """Test getting supported languages."""
        from app.services.language_detector import LanguageDetector
        
        detector = LanguageDetector()
        supported = detector.get_supported_languages()
        
        assert 'en' in supported
        assert 'es' in supported
        assert 'fr' in supported
        assert supported['en'] == 'English'
    
    def test_get_spacy_model(self):
        """Test getting spaCy model for language."""
        from app.services.language_detector import LanguageDetector
        
        detector = LanguageDetector()
        
        model = detector.get_spacy_model('en')
        assert model == 'en_core_web_sm'
        
        model = detector.get_spacy_model('xx')  # Unknown language
        assert model is None


class TestPlagiarismDetector:
    """Tests for PlagiarismDetector service."""
    
    def test_preprocess_text(self):
        """Test text preprocessing."""
        from app.services.plagiarism_detector import PlagiarismDetector
        
        detector = PlagiarismDetector()
        
        text = "  This   has   extra    spaces!   "
        result = detector._preprocess_text(text)
        
        assert "   " not in result
        assert result == "this has extra spaces"
    
    def test_create_shingles(self):
        """Test shingle creation."""
        from app.services.plagiarism_detector import PlagiarismDetector
        
        detector = PlagiarismDetector(shingle_size=3)
        
        text = "one two three four five"
        shingles = detector._create_shingles(text)
        
        assert len(shingles) > 0
        assert "one two three" in shingles
    
    def test_index_stats(self):
        """Test getting index statistics."""
        from app.services.plagiarism_detector import PlagiarismDetector
        
        detector = PlagiarismDetector()
        stats = detector.get_index_stats()
        
        assert "documents_indexed" in stats
        assert "threshold" in stats
        assert "shingle_size" in stats


class TestReviewerMatcher:
    """Tests for ReviewerMatcher service."""
    
    def test_keyword_similarity(self):
        """Test keyword similarity calculation."""
        from app.services.reviewer_matcher import ReviewerMatcher
        
        matcher = ReviewerMatcher()
        
        manuscript_keywords = ["machine learning", "neural networks", "deep learning"]
        reviewer_keywords = ["machine learning", "artificial intelligence", "deep learning"]
        
        score, matched = matcher.calculate_keyword_similarity(
            manuscript_keywords,
            reviewer_keywords
        )
        
        assert score > 0
        assert "machine learning" in matched or "deep learning" in matched
    
    def test_empty_keywords(self):
        """Test similarity with empty keywords."""
        from app.services.reviewer_matcher import ReviewerMatcher
        
        matcher = ReviewerMatcher()
        
        score, matched = matcher.calculate_keyword_similarity([], ["test"])
        assert score == 0.0
        assert matched == []
        
        score, matched = matcher.calculate_keyword_similarity(["test"], [])
        assert score == 0.0
        assert matched == []
    
    def test_hybrid_score(self):
        """Test hybrid score calculation."""
        from app.services.reviewer_matcher import ReviewerMatcher
        
        matcher = ReviewerMatcher()
        
        score = matcher.calculate_hybrid_score(
            keyword_score=0.8,
            semantic_score=0.6,
            keyword_weight=0.5
        )
        
        expected = (0.8 * 0.5) + (0.6 * 0.5)
        assert score == expected
