from django.db import models
from django.core.validators import MinLengthValidator
import json


class ManuscriptAnalysis(models.Model):
    """
    Store manuscript analysis results for tracking and improvement.
    """
    # Input information
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    input_type = models.CharField(
        max_length=10, 
        choices=[('text', 'Text'), ('pdf', 'PDF')],
        default='text'
    )
    manuscript_text = models.TextField(validators=[MinLengthValidator(50)])
    
    # Analysis results
    summary = models.TextField()
    keywords = models.JSONField(default=list)
    language_quality = models.JSONField(default=dict)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Manuscript Analysis"
        verbose_name_plural = "Manuscript Analyses"
    
    def __str__(self):
        filename = self.original_filename or "Text Input"
        return f"Analysis of {filename} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def word_count(self):
        """Get word count from language quality data."""
        return self.language_quality.get('word_count', 0)
    
    @property
    def readability_score(self):
        """Get readability score from language quality data."""
        return self.language_quality.get('readability_score', 0)


class ProcessingError(models.Model):
    """
    Log processing errors for debugging and improvement.
    """
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    input_type = models.CharField(
        max_length=10, 
        choices=[('text', 'Text'), ('pdf', 'PDF')],
        default='text'
    )
    input_size = models.IntegerField()  # character count or file size
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.error_type} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
