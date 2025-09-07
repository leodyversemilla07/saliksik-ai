from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.shortcuts import render
import logging

logger = logging.getLogger(__name__)


def homepage(request):
    """
    Render the interactive homepage with demo functionality.
    """
    return render(request, 'homepage.html')


@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """
    API information and documentation endpoint.
    """
    return Response({
        "name": "Saliksik AI - Manuscript Pre-Review System",
        "version": "1.0.0",
        "description": "AI-powered manuscript pre-review system with comprehensive text analysis",
        "features": [
            "AI-powered summarization using BART model",
            "Keyword extraction with TF-IDF",
            "Language quality analysis",
            "PDF text extraction",
            "User authentication system",
            "Rate limiting and security controls"
        ],
        "endpoints": {
            "web_interface": {
                "homepage": "/ [GET] - Interactive web interface",
                "api_info": "/api/info/ [GET] - This JSON endpoint"
            },
            "authentication": {
                "register": "/auth/register/ [POST]",
                "login": "/auth/login/ [POST]",
                "logout": "/auth/logout/ [POST]",
                "profile": "/auth/profile/ [GET]"
            },
            "analysis": {
                "demo": "/demo/ [POST] - Public demo (no auth required)",
                "pre_review": "/pre_review/ [POST] - Full analysis (auth required)"
            },
            "admin": "/admin/ [GET] - Django admin interface"
        },
        "demo_example": {
            "url": "/demo/",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json"
            },
            "body": {
                "manuscript_text": "Your manuscript text here (max 5000 characters)"
            }
        },
        "authentication_example": {
            "register": {
                "url": "/auth/register/",
                "method": "POST",
                "body": {
                    "username": "your_username",
                    "email": "your_email@example.com",
                    "password": "your_secure_password"
                }
            },
            "login": {
                "url": "/auth/login/",
                "method": "POST", 
                "body": {
                    "username": "your_username",
                    "password": "your_password"
                }
            },
            "authenticated_request": {
                "url": "/pre_review/",
                "method": "POST",
                "headers": {
                    "Authorization": "Token your_auth_token_here",
                    "Content-Type": "application/json"
                },
                "body": {
                    "manuscript_text": "Your manuscript text here"
                }
            }
        },
        "limits": {
            "demo": {
                "max_text_length": 5000,
                "file_upload": False,
                "rate_limit": "10/hour for anonymous users"
            },
            "authenticated": {
                "max_file_size": "10MB",
                "max_text_length": 50000,
                "rate_limit": "100/hour for authenticated users"
            }
        },
        "response_format": {
            "summary": "AI-generated summary of the manuscript",
            "keywords": ["list", "of", "extracted", "keywords"],
            "language_quality": {
                "word_count": "number",
                "unique_words": "number", 
                "sentence_count": "number",
                "named_entities": "number",
                "grammar_issues": "number (if Java/LanguageTool available)",
                "readability_score": "number (Flesch Reading Ease)"
            },
            "metadata": {
                "analysis_id": "number (authenticated only)",
                "input_length": "number",
                "processing_time": "number (seconds)",
                "user": "username (authenticated only)",
                "timestamp": "ISO datetime (authenticated only)"
            }
        },
        "status": {
            "server": "online",
            "debug_mode": settings.DEBUG,
            "language_tool_available": hasattr(settings, 'LANGUAGE_TOOL_AVAILABLE') and settings.LANGUAGE_TOOL_AVAILABLE
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Simple health check endpoint for monitoring.
    """
    return Response({
        "status": "healthy",
        "timestamp": request.META.get('HTTP_DATE'),
        "version": "1.0.0"
    }, status=status.HTTP_200_OK)
