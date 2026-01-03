"""
Celery configuration and tasks for FastAPI.
"""
from celery import Celery
from kombu import Queue
from app.core.config import settings

celery_app = Celery(
    "saliksik_ai",
    broker=settings.CELERY_BROKER_URL or "redis://localhost:6379/1",
    backend=settings.CELERY_RESULT_BACKEND or "redis://localhost:6379/1"
)

celery_app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task execution settings
    task_soft_time_limit=300,  # 5 minutes soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=360,       # 6 minutes hard limit (kills the task)
    task_acks_late=True,       # Acknowledge after task completes (safer for retries)
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    
    # Retry settings (defaults, can be overridden per-task)
    task_default_retry_delay=60,  # 1 minute default retry delay
    task_max_retries=3,           # Max 3 retries by default
    
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store task args and kwargs in result
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time (fair distribution)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)
    
    # Queue configuration
    task_queues=(
        Queue('default', routing_key='default'),
        Queue('analysis', routing_key='analysis.#'),
        Queue('low_priority', routing_key='low.#'),
    ),
    task_default_queue='default',
    task_routes={
        'app.tasks.analysis.*': {'queue': 'analysis'},
    },
)


class TaskPriority:
    """Task priority levels."""
    HIGH = 0
    NORMAL = 5
    LOW = 9
