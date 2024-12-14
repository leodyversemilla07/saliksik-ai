from django.http import JsonResponse
from rest_framework.decorators import api_view
from .ai_processor import ManuscriptPreReviewer

# Initialize the pre-reviewer class
pre_reviewer = ManuscriptPreReviewer()


@api_view(["POST"])
def pre_review(request):
    try:
        # Check for uploaded file or text input
        manuscript_file = request.FILES.get("manuscript_file", None)
        manuscript_text = request.data.get("manuscript_text", None)

        if manuscript_file:
            manuscript_text = pre_reviewer.extract_text_from_pdf(manuscript_file)
        elif not manuscript_text:
            return JsonResponse(
                {"error": "Manuscript text or file is required."}, status=400
            )

        # Generate the AI-assisted pre-review report
        report = pre_reviewer.generate_report(manuscript_text)
        return JsonResponse(report, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
