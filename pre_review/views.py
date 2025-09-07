from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging
from .ai_processor import ManuscriptPreReviewer

# Configure logging
logger = logging.getLogger(__name__)

# Initialize the pre-reviewer class
pre_reviewer = ManuscriptPreReviewer()


@api_view(["POST"])
def pre_review(request):
    """
    AI-assisted manuscript pre-review endpoint.
    
    Accepts either a PDF file upload or direct text input and returns
    a comprehensive analysis including summary, keywords, and language quality metrics.
    """
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
        logger.info(f"Processing manuscript with {len(manuscript_text)} characters")
        report = pre_reviewer.generate_report(manuscript_text)
        
        # Add metadata to response
        report["metadata"] = {
            "input_length": len(manuscript_text),
            "processing_timestamp": request.META.get('HTTP_DATE', 'Unknown')
        }
        
        return Response(report, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Unexpected error in pre_review: {str(e)}", exc_info=True)
        return Response(
            {
                "error": "Internal server error occurred during processing.",
                "details": "Please try again or contact support if the issue persists."
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
