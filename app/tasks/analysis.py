import logging
import time
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.analysis import ManuscriptAnalysis
from app.services.ai_processor import ManuscriptPreReviewer
from app.core.cache import AIResultCache

logger = logging.getLogger(__name__)

# Initialize AI processor (lazy loaded in worker)
pre_reviewer = ManuscriptPreReviewer()

@celery_app.task(bind=True)
def process_manuscript_task(self, analysis_id: int, text: str):
    """
    Background task to process manuscript analysis.
    """
    db: Session = SessionLocal()
    start_time = time.time()
    
    try:
        # Get analysis record
        analysis = db.query(ManuscriptAnalysis).filter(ManuscriptAnalysis.id == analysis_id).first()
        if not analysis:
            logger.error(f"Analysis ID {analysis_id} not found")
            return
        
        # Update status to PROCESSING
        analysis.status = 'PROCESSING'
        analysis.task_id = self.request.id
        db.commit()
        
        logger.info(f"Starting analysis for ID {analysis_id}")
        
        # Run AI processing
        report = pre_reviewer.generate_report(text)
        processing_time = time.time() - start_time
        
        # Update record with results
        analysis.summary = report['summary']
        analysis.keywords = report['keywords']
        analysis.language_quality = report['language_quality']
        analysis.processing_time = processing_time
        analysis.status = 'COMPLETED'
        
        db.commit()
        
        # Cache result
        # We reconstruct the response format for caching
        cache_data = {
            "summary": report['summary'],
            "keywords": report['keywords'],
            "language_quality": report['language_quality'],
            "metadata": {
                "analysis_id": analysis.id,
                "input_length": len(text),
                "processing_time": round(processing_time, 2),
                "user": analysis.user.username if analysis.user else "unknown",
                "timestamp": analysis.created_at.isoformat(),
                "cached": False
            }
        }
        AIResultCache.cache_result(text, cache_data)
        
        logger.info(f"Analysis {analysis_id} completed in {processing_time:.2f}s")
        return "Success"
        
    except Exception as e:
        logger.error(f"Task failed: {str(e)}", exc_info=True)
        if analysis:
            analysis.status = 'FAILED'
            db.commit()
        raise e
    finally:
        db.close()
