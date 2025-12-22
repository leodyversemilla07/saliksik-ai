"""
API v1 router aggregation.
"""
from fastapi import APIRouter
from app.api.v1 import auth, analysis, info

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(info.router, tags=["Info"])
