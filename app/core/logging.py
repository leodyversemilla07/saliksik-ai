"""
Structured logging configuration with JSON format and request tracking.
"""
import logging
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from contextvars import ContextVar
from functools import wraps

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id
        
        # Add extra fields from record
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class StandardFormatter(logging.Formatter):
    """Standard formatter with request ID support."""
    
    def format(self, record: logging.LogRecord) -> str:
        request_id = get_request_id()
        if request_id:
            record.request_id = request_id[:8]  # Short ID for readability
        else:
            record.request_id = "--------"
        return super().format(record)


def setup_logging(json_format: bool = False) -> None:
    """
    Configure application logging.
    
    Args:
        json_format: Use JSON format (recommended for production)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(StandardFormatter(
            fmt="%(asctime)s [%(request_id)s] %(levelname)-8s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


class StructuredLogger:
    """Logger wrapper that supports structured extra data."""
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
    
    def _log(self, level: int, msg: str, extra_data: Optional[dict] = None, **kwargs):
        if extra_data:
            kwargs.setdefault("extra", {})["extra_data"] = extra_data
        self._logger.log(level, msg, **kwargs)
    
    def debug(self, msg: str, extra: Optional[dict] = None, **kwargs):
        self._log(logging.DEBUG, msg, extra, **kwargs)
    
    def info(self, msg: str, extra: Optional[dict] = None, **kwargs):
        self._log(logging.INFO, msg, extra, **kwargs)
    
    def warning(self, msg: str, extra: Optional[dict] = None, **kwargs):
        self._log(logging.WARNING, msg, extra, **kwargs)
    
    def error(self, msg: str, extra: Optional[dict] = None, **kwargs):
        self._log(logging.ERROR, msg, extra, **kwargs)
    
    def critical(self, msg: str, extra: Optional[dict] = None, **kwargs):
        self._log(logging.CRITICAL, msg, extra, **kwargs)
    
    def exception(self, msg: str, extra: Optional[dict] = None, **kwargs):
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, extra, **kwargs)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request logging with timing and request ID tracking.
    """
    
    EXCLUDE_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/api/openapi.json"}
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        
        # Skip logging for excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        
        logger = get_logger("api.request")
        start_time = time.perf_counter()
        
        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "extra_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent", ""),
                }
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "extra_data": {
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                    }
                },
                exc_info=True
            )
            raise
        
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "extra_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            }
        )
        
        # Add headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response


def log_function_call(logger_name: str = "app"):
    """
    Decorator to log function entry/exit with timing.
    
    Usage:
        @log_function_call("mymodule")
        def my_function(arg1, arg2):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            start = time.perf_counter()
            logger.debug(f"Entering {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                logger.debug(f"Exiting {func.__name__} ({duration:.2f}ms)")
                return result
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                logger.error(f"Error in {func.__name__} ({duration:.2f}ms): {e}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            start = time.perf_counter()
            logger.debug(f"Entering {func.__name__}")
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                logger.debug(f"Exiting {func.__name__} ({duration:.2f}ms)")
                return result
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                logger.error(f"Error in {func.__name__} ({duration:.2f}ms): {e}")
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
