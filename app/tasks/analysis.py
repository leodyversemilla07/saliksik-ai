"""
Background tasks for manuscript analysis.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional
from celery import states
from celery.exceptions import SoftTimeLimitExceeded, MaxRetriesExceededError
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.analysis import ManuscriptAnalysis, ProcessingError
from app.services.ai_processor import ManuscriptPreReviewer
from app.core.cache import AIResultCache

logger = logging.getLogger(__name__)

# Retry configuration
RETRY_BACKOFF = True  # Use exponential backoff
RETRY_BACKOFF_MAX = 600  # Max 10 minutes between retries
RETRY_JITTER = True  # Add randomness to prevent thundering herd

# Initialize AI processor (lazy loaded in worker)
pre_reviewer = None


def get_pre_reviewer():
    """Lazy initialization of AI processor."""
    global pre_reviewer
    if pre_reviewer is None:
        pre_reviewer = ManuscriptPreReviewer()
    return pre_reviewer


def log_processing_error(
    db: Session,
    error_type: str,
    error_message: str,
    input_type: str = "text",
    input_size: int = 0,
):
    """Log a processing error to the database."""
    try:
        error = ProcessingError(
            error_type=error_type,
            error_message=error_message[:1000],  # Truncate long messages
            input_type=input_type,
            input_size=input_size,
        )
        db.add(error)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log processing error: {e}")


@celery_app.task(
    bind=True,
    name="app.tasks.analysis.process_manuscript_task",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes hard limit
    autoretry_for=(Exception,),
    retry_backoff=RETRY_BACKOFF,
    retry_backoff_max=RETRY_BACKOFF_MAX,
    retry_jitter=RETRY_JITTER,
)
def process_manuscript_task(self, analysis_id: int, text: str):
    """
    Background task to process manuscript analysis.

    Features:
    - Automatic retry with exponential backoff
    - Soft/hard time limits
    - Error tracking to database
    - Progress updates via task state
    """
    db: Session = SessionLocal()
    start_time = time.time()
    analysis: Optional[ManuscriptAnalysis] = None

    try:
        # Get analysis record
        analysis = (
            db.query(ManuscriptAnalysis)
            .filter(ManuscriptAnalysis.id == analysis_id)
            .first()
        )

        if not analysis:
            logger.error(f"Analysis ID {analysis_id} not found")
            return {"status": "error", "message": "Analysis not found"}

        # Update status to PROCESSING with retry info
        retry_count = self.request.retries
        analysis.status = "PROCESSING"
        analysis.task_id = self.request.id
        db.commit()

        # Update task state for progress tracking
        self.update_state(
            state="PROCESSING",
            meta={
                "analysis_id": analysis_id,
                "retry": retry_count,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            f"Starting analysis for ID {analysis_id} "
            f"(attempt {retry_count + 1}/{self.max_retries + 1})"
        )

        # Run AI processing
        processor = get_pre_reviewer()
        report = processor.generate_report(text)
        processing_time = time.time() - start_time

        # Update record with results
        analysis.summary = report["summary"]
        analysis.keywords = report["keywords"]
        analysis.language_quality = report["language_quality"]
        analysis.processing_time = processing_time
        analysis.status = "COMPLETED"
        db.commit()

        # Cache result
        cache_data = {
            "summary": report["summary"],
            "keywords": report["keywords"],
            "language_quality": report["language_quality"],
            "metadata": {
                "analysis_id": analysis.id,
                "input_length": len(text),
                "processing_time": round(processing_time, 2),
                "user": analysis.user.username if analysis.user else "unknown",
                "timestamp": analysis.created_at.isoformat(),
                "cached": False,
            },
        }
        AIResultCache.cache_result(text, cache_data)

        logger.info(f"Analysis {analysis_id} completed in {processing_time:.2f}s")

        return {
            "status": "success",
            "analysis_id": analysis_id,
            "processing_time": round(processing_time, 2),
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"Analysis {analysis_id} exceeded soft time limit")
        if analysis:
            analysis.status = "TIMEOUT"
            db.commit()
        log_processing_error(
            db,
            error_type="TIMEOUT",
            error_message="Task exceeded time limit",
            input_size=len(text),
        )
        raise  # Let Celery handle the timeout

    except MaxRetriesExceededError:
        logger.error(f"Analysis {analysis_id} failed after max retries")
        if analysis:
            analysis.status = "FAILED"
            db.commit()
        log_processing_error(
            db,
            error_type="MAX_RETRIES",
            error_message="Task failed after maximum retry attempts",
            input_size=len(text),
        )
        return {"status": "failed", "message": "Max retries exceeded"}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task failed: {error_msg}", exc_info=True)

        # Check if we should retry
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying analysis {analysis_id} "
                f"(attempt {retry_count + 2}/{self.max_retries + 1})"
            )
            if analysis:
                analysis.status = "RETRYING"
                db.commit()
            raise  # Celery will auto-retry due to autoretry_for

        # Max retries reached
        if analysis:
            analysis.status = "FAILED"
            db.commit()

        log_processing_error(
            db,
            error_type=type(e).__name__,
            error_message=error_msg,
            input_size=len(text),
        )

        return {"status": "failed", "message": error_msg[:200]}

    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.tasks.analysis.cleanup_stale_analyses",
    max_retries=1,
)
def cleanup_stale_analyses(self, hours: int = 24):
    """
    Cleanup task to mark stale PROCESSING analyses as FAILED.

    Run periodically via Celery Beat:
    celery_app.conf.beat_schedule = {
        'cleanup-stale': {
            'task': 'app.tasks.analysis.cleanup_stale_analyses',
            'schedule': 3600.0,  # Every hour
        },
    }
    """
    from datetime import timedelta

    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Find stale analyses
        stale = (
            db.query(ManuscriptAnalysis)
            .filter(
                ManuscriptAnalysis.status.in_(["PROCESSING", "PENDING", "RETRYING"]),
                ManuscriptAnalysis.created_at < cutoff,
            )
            .all()
        )

        count = 0
        for analysis in stale:
            analysis.status = "FAILED"
            count += 1
            logger.warning(f"Marked stale analysis {analysis.id} as FAILED")

        if count > 0:
            db.commit()
            logger.info(f"Cleaned up {count} stale analyses")

        return {"cleaned": count}

    except Exception as e:
        logger.error(f"Cleanup task failed: {e}", exc_info=True)
        raise
    finally:
        db.close()
