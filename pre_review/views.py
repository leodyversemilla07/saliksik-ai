from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import logging
import time
from .ai_processor import ManuscriptPreReviewer
from .models import ManuscriptAnalysis, ProcessingError

# Configure logging
logger = logging.getLogger(__name__)

# Initialize the pre-reviewer class
pre_reviewer = ManuscriptPreReviewer()


@api_view(["POST"])
def pre_review(request):
    """
    AI-assisted manuscript pre-review endpoint (authenticated).
    
    Accepts either a PDF file upload or direct text input and returns
    a comprehensive analysis including summary, keywords, and language quality metrics.
    """
    start_time = time.time()
    
    try:
        # Input validation
        manuscript_file = request.FILES.get("manuscript_file", None)
        manuscript_text = request.data.get("manuscript_text", None)

        if not manuscript_file and not manuscript_text:
            return Response(
                {
                    "error": "Either 'manuscript_file' (PDF) or 'manuscript_text' is required.",
                    "details": "Please provide either a PDF file or text content for analysis."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle file upload
        if manuscript_file:
            # Validate file type
            if not manuscript_file.name.lower().endswith('.pdf'):
                return Response(
                    {
                        "error": "Invalid file type. Only PDF files are supported.",
                        "details": f"Received file: {manuscript_file.name}"
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file size (10MB limit)
            if manuscript_file.size > 10 * 1024 * 1024:
                return Response(
                    {
                        "error": "File too large. Maximum size is 10MB.",
                        "details": f"File size: {manuscript_file.size / (1024*1024):.2f}MB"
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                manuscript_text = pre_reviewer.extract_text_from_pdf(manuscript_file)
                if not manuscript_text.strip():
                    return Response(
                        {
                            "error": "Unable to extract text from PDF.",
                            "details": "The PDF appears to be empty or contains only images."
                        }, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as pdf_error:
                logger.error(f"PDF extraction error: {str(pdf_error)}")
                return Response(
                    {
                        "error": "Failed to process PDF file.",
                        "details": "The PDF file may be corrupted or password-protected."
                    }, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validate text length
        if len(manuscript_text.strip()) < 50:
            return Response(
                {
                    "error": "Text too short for meaningful analysis.",
                    "details": "Please provide at least 50 characters of text."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate the AI-assisted pre-review report
        logger.info(f"Processing manuscript with {len(manuscript_text)} characters for user {request.user.username}")
        report = pre_reviewer.generate_report(manuscript_text)
        
        processing_time = time.time() - start_time
        
        # Save analysis to database
        try:
            analysis = ManuscriptAnalysis.objects.create(
                original_filename=manuscript_file.name if manuscript_file else None,
                input_type='pdf' if manuscript_file else 'text',
                manuscript_text=manuscript_text[:10000],  # Store first 10k chars only
                summary=report['summary'],
                keywords=report['keywords'],
                language_quality=report['language_quality'],
                processing_time=processing_time
            )
            
            # Add metadata to response
            report["metadata"] = {
                "analysis_id": analysis.id,
                "input_length": len(manuscript_text),
                "processing_time": round(processing_time, 2),
                "user": request.user.username,
                "timestamp": analysis.created_at.isoformat()
            }
        except Exception as db_error:
            logger.error(f"Database save error: {str(db_error)}")
            # Continue without saving to DB
            report["metadata"] = {
                "input_length": len(manuscript_text),
                "processing_time": round(processing_time, 2),
                "user": request.user.username,
                "note": "Analysis not saved to database"
            }
        
        return Response(report, status=status.HTTP_200_OK)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Unexpected error in pre_review: {str(e)}", exc_info=True)
        
        # Log error to database
        try:
            ProcessingError.objects.create(
                error_type=type(e).__name__,
                error_message=str(e),
                input_type='pdf' if manuscript_file else 'text',
                input_size=manuscript_file.size if manuscript_file else len(manuscript_text or '')
            )
        except:
            pass  # Don't fail if we can't log the error
        
        return Response(
            {
                "error": "Internal server error occurred during processing.",
                "details": "Please try again or contact support if the issue persists.",
                "processing_time": round(processing_time, 2)
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def demo_pre_review(request):
    """
    Public demo endpoint for testing without authentication.
    Limited to text input only and shorter texts.
    """
    start_time = time.time()
    
    try:
        manuscript_text = request.data.get("manuscript_text", None)

        if not manuscript_text:
            return Response(
                {
                    "error": "Demo requires text input only.",
                    "details": "Please provide 'manuscript_text' for analysis. File uploads not supported in demo."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Demo limitations
        if len(manuscript_text.strip()) < 50:
            return Response(
                {
                    "error": "Text too short for meaningful analysis.",
                    "details": "Please provide at least 50 characters of text."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if len(manuscript_text) > 5000:
            return Response(
                {
                    "error": "Text too long for demo.",
                    "details": "Demo is limited to 5000 characters. Please register for full access."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate the AI-assisted pre-review report
        logger.info(f"Processing demo manuscript with {len(manuscript_text)} characters")
        report = pre_reviewer.generate_report(manuscript_text)
        
        processing_time = time.time() - start_time
        
        # Add demo metadata
        report["metadata"] = {
            "demo": True,
            "input_length": len(manuscript_text),
            "processing_time": round(processing_time, 2),
            "limitations": "Demo version - register for full features"
        }
        
        return Response(report, status=status.HTTP_200_OK)

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Unexpected error in demo_pre_review: {str(e)}", exc_info=True)
        
        return Response(
            {
                "error": "Internal server error occurred during processing.",
                "details": "Please try again or contact support if the issue persists.",
                "processing_time": round(processing_time, 2)
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
