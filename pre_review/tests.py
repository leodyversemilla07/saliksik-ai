from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
import json
from .ai_processor import ManuscriptPreReviewer
from .models import ManuscriptAnalysis, ProcessingError


class ManuscriptPreReviewerTests(TestCase):
    """Test the AI processor functionality."""
    
    def setUp(self):
        self.processor = ManuscriptPreReviewer()
        self.sample_text = """
        Artificial Intelligence (AI) is rapidly transforming the field of technology. 
        This manuscript discusses various advancements in AI, including neural networks, 
        machine learning, and their applications in real-world scenarios. The research 
        presents novel approaches to deep learning architectures and their implementation 
        in practical applications.
        """
    
    def test_preprocess_text(self):
        """Test text preprocessing functionality."""
        text = "  This   is   a   test   text.  "
        processed = self.processor.preprocess_text(text)
        self.assertEqual(processed, "This is a test text.")
    
    def test_extract_keywords(self):
        """Test keyword extraction."""
        keywords = self.processor.extract_keywords(self.sample_text, top_n=5)
        self.assertIsInstance(keywords, list)
        self.assertLessEqual(len(keywords), 5)
        self.assertTrue(all(isinstance(keyword, str) for keyword in keywords))
    
    def test_assess_language_quality(self):
        """Test language quality assessment."""
        quality = self.processor.assess_language_quality(self.sample_text)
        self.assertIn('word_count', quality)
        self.assertIn('unique_words', quality)
        self.assertIn('sentence_count', quality)
        self.assertIn('readability_score', quality)
        self.assertGreater(quality['word_count'], 0)
    
    @patch('pre_review.ai_processor.ManuscriptPreReviewer.generate_summary')
    def test_generate_report(self, mock_summarize):
        """Test complete report generation."""
        mock_summarize.return_value = "Mocked summary"
        
        report = self.processor.generate_report(self.sample_text)
        
        self.assertIn('summary', report)
        self.assertIn('keywords', report)
        self.assertIn('language_quality', report)
        self.assertEqual(report['summary'], "Mocked summary")


class PreReviewAPITests(TestCase):
    """Test the API endpoint functionality."""
    
    def setUp(self):
        self.client = Client()
        self.url = reverse('pre_review')
        self.sample_text = """
        This is a sample manuscript text for testing purposes. It contains multiple 
        sentences to ensure proper processing. The text discusses various topics 
        related to artificial intelligence and machine learning applications.
        """
    
    def test_pre_review_with_text_success(self):
        """Test successful pre-review with text input."""
        with patch('pre_review.views.pre_reviewer.generate_report') as mock_report:
            mock_report.return_value = {
                'summary': 'Test summary',
                'keywords': ['test', 'sample'],
                'language_quality': {'word_count': 50}
            }
            
            response = self.client.post(self.url, {
                'manuscript_text': self.sample_text
            })
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('summary', data)
            self.assertIn('keywords', data)
            self.assertIn('language_quality', data)
            self.assertIn('metadata', data)
    
    def test_pre_review_missing_input(self):
        """Test API response when no input is provided."""
        response = self.client.post(self.url, {})
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
    
    def test_pre_review_short_text(self):
        """Test API response with text that's too short."""
        response = self.client.post(self.url, {
            'manuscript_text': 'Short text'
        })
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('too short', data['error'])
    
    def test_pre_review_invalid_file_type(self):
        """Test API response with invalid file type."""
        fake_file = SimpleUploadedFile(
            "test.txt", 
            b"file content", 
            content_type="text/plain"
        )
        
        response = self.client.post(self.url, {
            'manuscript_file': fake_file
        })
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('Invalid file type', data['error'])
    
    def test_pre_review_large_file(self):
        """Test API response with file that's too large."""
        # Create a large fake PDF (over 10MB)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        fake_file = SimpleUploadedFile(
            "large_test.pdf", 
            large_content, 
            content_type="application/pdf"
        )
        
        response = self.client.post(self.url, {
            'manuscript_file': fake_file
        })
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('File too large', data['error'])


class ModelTests(TestCase):
    """Test database models."""
    
    def test_manuscript_analysis_creation(self):
        """Test creating a ManuscriptAnalysis record."""
        analysis = ManuscriptAnalysis.objects.create(
            manuscript_text="Test manuscript text for analysis.",
            input_type="text",
            summary="Test summary",
            keywords=["test", "analysis"],
            language_quality={"word_count": 50, "readability_score": 65.5}
        )
        
        self.assertEqual(analysis.input_type, "text")
        self.assertEqual(analysis.word_count, 50)
        self.assertEqual(analysis.readability_score, 65.5)
        self.assertIn("Text Input", str(analysis))
    
    def test_processing_error_creation(self):
        """Test creating a ProcessingError record."""
        error = ProcessingError.objects.create(
            error_type="ValidationError",
            error_message="Test error message",
            input_type="pdf",
            input_size=1024
        )
        
        self.assertEqual(error.error_type, "ValidationError")
        self.assertEqual(error.input_size, 1024)
        self.assertIn("ValidationError", str(error))
