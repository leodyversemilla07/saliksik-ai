from django.contrib import admin
from .models import ManuscriptAnalysis, ProcessingError


@admin.register(ManuscriptAnalysis)
class ManuscriptAnalysisAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'input_type', 'word_count', 'readability_score', 'created_at')
    list_filter = ('input_type', 'created_at')
    search_fields = ('original_filename', 'summary')
    readonly_fields = ('created_at', 'processing_time')
    
    fieldsets = (
        ('Input Information', {
            'fields': ('original_filename', 'input_type', 'manuscript_text')
        }),
        ('Analysis Results', {
            'fields': ('summary', 'keywords', 'language_quality')
        }),
        ('Metadata', {
            'fields': ('created_at', 'processing_time'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProcessingError)
class ProcessingErrorAdmin(admin.ModelAdmin):
    list_display = ('error_type', 'input_type', 'input_size', 'created_at')
    list_filter = ('error_type', 'input_type', 'created_at')
    search_fields = ('error_message',)
    readonly_fields = ('created_at',)
