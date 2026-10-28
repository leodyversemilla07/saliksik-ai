"""
Shared OpenAPI response documentation.

The application returns a single error envelope for every failure:

```json
{"error": {"code": "HTTP_ERROR", "message": "..."}}
```

The helpers below document that envelope in the generated OpenAPI schema so
the interactive docs match the runtime behaviour.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Body of the standard error envelope."""

    code: str = Field(..., description="Machine readable error code", examples=["HTTP_ERROR"])
    message: str = Field(..., description="Human readable error message", examples=["Not authenticated"])
    details: Optional[Dict[str, Any]] = Field(None, description="Optional structured error details")


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorBody


def _error_response(description: str, code: str, message: str) -> Dict[str, Any]:
    """Build an OpenAPI response definition for the error envelope."""
    return {
        "description": description,
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {
                    "error": {
                        "code": code,
                        "message": message,
                    }
                }
            }
        },
    }


# Common error responses
UNAUTHORIZED_RESPONSE = _error_response("Authentication required", "HTTP_ERROR", "Not authenticated")
FORBIDDEN_RESPONSE = _error_response("Permission denied", "HTTP_ERROR", "Not enough permissions")
NOT_FOUND_RESPONSE = _error_response("Resource not found", "HTTP_ERROR", "Resource not found")
VALIDATION_ERROR_RESPONSE = _error_response("Validation error", "VALIDATION_ERROR", "Request validation failed")
RATE_LIMIT_RESPONSE = _error_response(
    "Rate limit exceeded", "RATE_LIMIT_EXCEEDED", "Rate limit exceeded. Try again in 60 seconds."
)
SERVER_ERROR_RESPONSE = _error_response("Internal server error", "INTERNAL_ERROR", "An unexpected error occurred")
SERVICE_UNAVAILABLE_RESPONSE = _error_response(
    "Service unavailable", "SERVICE_UNAVAILABLE", "The service is currently unavailable"
)
PAYLOAD_TOO_LARGE_RESPONSE = _error_response("Payload too large", "HTTP_ERROR", "Text exceeds maximum allowed length")

# Responses shared by every authenticated endpoint.
COMMON_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    401: UNAUTHORIZED_RESPONSE,
    403: FORBIDDEN_RESPONSE,
    404: NOT_FOUND_RESPONSE,
    422: VALIDATION_ERROR_RESPONSE,
    429: RATE_LIMIT_RESPONSE,
    500: SERVER_ERROR_RESPONSE,
}


def error_examples(*examples: Dict[str, Any]) -> Dict[str, Any]:
    """Build an OpenAPI response definition with named examples.

    Args:
        examples: Mapping of a summary to the error payload.

    Returns:
        An OpenAPI response definition using the standard error envelope.
    """
    return {
        "description": ", ".join(example.get("summary", "Error") for example in examples),
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "examples": {
                    example["summary"]: {
                        "summary": example["summary"],
                        "value": {"error": {"code": example.get("code", "HTTP_ERROR"), "message": example["message"]}},
                    }
                    for example in examples
                }
            }
        },
    }


__all__: List[str] = [
    "COMMON_RESPONSES",
    "ErrorBody",
    "ErrorResponse",
    "FORBIDDEN_RESPONSE",
    "NOT_FOUND_RESPONSE",
    "PAYLOAD_TOO_LARGE_RESPONSE",
    "RATE_LIMIT_RESPONSE",
    "SERVICE_UNAVAILABLE_RESPONSE",
    "SERVER_ERROR_RESPONSE",
    "UNAUTHORIZED_RESPONSE",
    "VALIDATION_ERROR_RESPONSE",
    "error_examples",
]
