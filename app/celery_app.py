"""
Celery configuration and tasks for FastAPI.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "saliksik_ai",
    broker=settings.CELERY_BROKER_URL or "redis://localhost:6379/1",
    backend=settings.CELERY_RESULT_BACKEND or "redis://localhost:6379/1"
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
