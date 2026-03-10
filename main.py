"""
FastAPI main application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base
from app.core.rate_limit import RateLimitMiddleware
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging, get_logger, RequestLoggingMiddleware
from app.core.security_utils import RequestSizeLimitMiddleware
from app.api.v1 import api_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Configure structured logging (use JSON in production)
setup_logging(json_format=not settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting up Saliksik AI...")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Saliksik AI...")


API_DESCRIPTION = """
# Saliksik AI - Manuscript Pre-Review System

AI-powered manuscript pre-review system for Research Journal Management.

## Features

* **Manuscript Analysis** - AI-powered summary, keyword extraction, and language quality assessment
* **Plagiarism Detection** - Check manuscripts against a database of existing documents
* **Reviewer Matching** - Find suitable reviewers based on expertise keywords and semantic similarity
* **Multi-language Support** - Support for English, Spanish, French, and German

## Authentication

Most endpoints require authentication via JWT Bearer token or API key.

### JWT Token
1. Register or login to get an access token
2. Include in header: `Authorization: Bearer <token>`

### API Key
1. Generate an API key via `/api/v1/auth/api-key`
2. Include in header: `X-API-Key: <key>`

## Rate Limiting

- Anonymous: 60 requests/hour
- Authenticated: 100 requests/hour

## Response Headers

All responses include:
- `X-Request-ID`: Unique request identifier for tracing
- `X-Response-Time`: Request processing time
"""

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    contact={
        "name": "Saliksik AI Support",
        "email": "support@saliksik.ai"
    },
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User registration, login, and token management"
        },
        {
            "name": "Analysis",
            "description": "Manuscript analysis and processing"
        },
        {
            "name": "Plagiarism Detection",
            "description": "Check manuscripts for potential plagiarism"
        },
        {
            "name": "Reviewer Matching",
            "description": "Manage reviewer profiles and find matching reviewers"
        },
        {
            "name": "Info",
            "description": "System information and health checks"
        }
    ]
)

# Register exception handlers
register_exception_handlers(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request size limit middleware (DoS protection)
app.add_middleware(RequestSizeLimitMiddleware)

# Request logging middleware (adds request ID and timing)
app.add_middleware(RequestLoggingMiddleware)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Inject security headers on every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns detailed status of all service dependencies.
    """
    from sqlalchemy import text
    
    health_status = {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": "development" if settings.DEBUG else "production",
        "services": {}
    }
    
    # Check database connectivity and pool status
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        
        from app.core.database import get_pool_status
        pool_status = get_pool_status()
        health_status["services"]["database"] = {
            "status": "healthy",
            "pool": pool_status
        }
    except Exception as e:
        health_status["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check Redis connectivity
    try:
        if settings.REDIS_URL:
            import redis
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            health_status["services"]["redis"] = {"status": "healthy"}
        else:
            health_status["services"]["redis"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["redis"] = {"status": "unhealthy", "error": str(e)}
        # Redis is optional, so just mark as degraded
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"
    
    # Check Celery broker (same as Redis usually)
    try:
        if settings.CELERY_BROKER_URL:
            health_status["services"]["celery_broker"] = {"status": "configured", "url": settings.CELERY_BROKER_URL.split("@")[-1] if "@" in settings.CELERY_BROKER_URL else "configured"}
        else:
            health_status["services"]["celery_broker"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["celery_broker"] = {"status": "error", "error": str(e)}
    
    # Add cache statistics
    try:
        from app.core.cache import AIResultCache
        health_status["services"]["cache"] = AIResultCache.get_cache_stats()
    except Exception as e:
        health_status["services"]["cache"] = {"status": "error", "error": str(e)}
    
    return health_status


# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the landing page."""
    index_file = os.path.join(static_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api": "/api/v1"
    }


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the dashboard page."""
    dashboard_file = os.path.join(static_path, "dashboard.html")
    if os.path.exists(dashboard_file):
        return FileResponse(dashboard_file)
    return {"error": "Dashboard page not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
