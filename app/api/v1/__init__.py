"""
API v1 router aggregation.
"""

from fastapi import APIRouter

from app.api.v1 import analysis, auth, info, plagiarism, reviewers

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(
    plagiarism.router, prefix="/plagiarism", tags=["Plagiarism Detection"]
)
api_router.include_router(
    reviewers.router, prefix="/reviewers", tags=["Reviewer Matching"]
)
api_router.include_router(info.router, tags=["Info"])
