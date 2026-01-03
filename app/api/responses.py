"""
Standardized API response models and examples for OpenAPI documentation.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# Common error response model
class ErrorDetail(BaseModel):
    """Standard error detail."""
    loc: Optional[List[str]] = Field(None, description="Location of the error")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Error description")


class ValidationErrorResponse(BaseModel):
    """Validation error response (422)."""
    detail: List[ErrorDetail] = Field(..., description="List of validation errors")


# Common response examples
UNAUTHORIZED_RESPONSE = {
    "description": "Authentication required",
    "content": {
        "application/json": {
            "example": {"detail": "Not authenticated"}
        }
    }
}

FORBIDDEN_RESPONSE = {
    "description": "Permission denied",
    "content": {
        "application/json": {
            "example": {"detail": "Not enough permissions"}
        }
    }
}

NOT_FOUND_RESPONSE = {
    "description": "Resource not found",
    "content": {
        "application/json": {
            "example": {"detail": "Resource not found"}
        }
    }
}

VALIDATION_ERROR_RESPONSE = {
    "description": "Validation error",
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "email"],
                        "msg": "Invalid email format",
                        "type": "value_error"
                    }
                ]
            }
        }
    }
}

RATE_LIMIT_RESPONSE = {
    "description": "Rate limit exceeded",
    "content": {
        "application/json": {
            "example": {"detail": "Rate limit exceeded. Try again in 60 seconds."}
        }
    }
}

SERVER_ERROR_RESPONSE = {
    "description": "Internal server error",
    "content": {
        "application/json": {
            "example": {"detail": "Internal server error"}
        }
    }
}


# Auth endpoint examples
AUTH_RESPONSES = {
    "register": {
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 10080,
                        "user": {
                            "id": 1,
                            "username": "researcher",
                            "email": "researcher@example.com",
                            "is_active": True,
                            "created_at": "2026-01-03T10:00:00Z",
                            "last_login": None
                        }
                    }
                }
            }
        },
        400: {
            "description": "Registration failed",
            "content": {
                "application/json": {
                    "examples": {
                        "duplicate": {
                            "summary": "User already exists",
                            "value": {"detail": "Username or email already registered"}
                        },
                        "weak_password": {
                            "summary": "Weak password",
                            "value": {"detail": "Password must be at least 8 characters"}
                        }
                    }
                }
            }
        },
        422: VALIDATION_ERROR_RESPONSE
    },
    "login": {
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 10080,
                        "user": {
                            "id": 1,
                            "username": "researcher",
                            "email": "researcher@example.com",
                            "is_active": True,
                            "created_at": "2026-01-03T10:00:00Z",
                            "last_login": "2026-01-03T14:30:00Z"
                        }
                    }
                }
            }
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {"detail": "Incorrect username or password"}
                }
            }
        }
    },
    "refresh": {
        200: {
            "description": "Token refreshed",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 10080
                    }
                }
            }
        },
        401: {
            "description": "Invalid refresh token",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid or expired refresh token"}
                }
            }
        }
    }
}


# Analysis endpoint examples
ANALYSIS_RESPONSES = {
    "submit": {
        202: {
            "description": "Analysis submitted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "abc123-def456-ghi789",
                        "analysis_id": 42,
                        "status": "PENDING",
                        "message": "Analysis started successfully. Poll /status/{task_id} for results."
                    }
                }
            }
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {
                    "examples": {
                        "no_input": {
                            "summary": "No input provided",
                            "value": {"detail": "Either 'manuscript_file' (PDF) or 'manuscript_text' is required"}
                        },
                        "too_short": {
                            "summary": "Text too short",
                            "value": {"detail": "Text too short for meaningful analysis (minimum 50 characters)"}
                        },
                        "invalid_pdf": {
                            "summary": "Invalid PDF",
                            "value": {"detail": "Unable to extract text from PDF"}
                        }
                    }
                }
            }
        },
        401: UNAUTHORIZED_RESPONSE
    },
    "status": {
        200: {
            "description": "Analysis status/result",
            "content": {
                "application/json": {
                    "examples": {
                        "completed": {
                            "summary": "Analysis completed",
                            "value": {
                                "summary": "This manuscript presents a novel approach to machine learning...",
                                "keywords": ["machine learning", "neural networks", "deep learning"],
                                "language_quality": {
                                    "score": 85,
                                    "readability_score": 45.2,
                                    "word_count": 5420,
                                    "sentence_count": 234,
                                    "issues": []
                                },
                                "metadata": {
                                    "analysis_id": 42,
                                    "input_length": 28500,
                                    "processing_time": 3.45,
                                    "user": "researcher",
                                    "timestamp": "2026-01-03T14:30:00Z",
                                    "cached": False
                                }
                            }
                        },
                        "processing": {
                            "summary": "Still processing",
                            "value": {
                                "task_id": "abc123-def456-ghi789",
                                "status": "PROCESSING",
                                "message": "Analysis in progress..."
                            }
                        },
                        "failed": {
                            "summary": "Analysis failed",
                            "value": {
                                "task_id": "abc123-def456-ghi789",
                                "status": "FAILED",
                                "message": "Analysis failed. Please try again."
                            }
                        }
                    }
                }
            }
        },
        404: NOT_FOUND_RESPONSE
    },
    "demo": {
        200: {
            "description": "Demo analysis result",
            "content": {
                "application/json": {
                    "example": {
                        "summary": "This text discusses the fundamentals of scientific research...",
                        "keywords": ["research", "methodology", "analysis"],
                        "language_quality": {
                            "score": 78,
                            "readability_score": 52.1,
                            "word_count": 850,
                            "sentence_count": 42,
                            "issues": ["Consider varying sentence length"]
                        },
                        "metadata": {
                            "input_length": 4200,
                            "processing_time": 1.23,
                            "cached": False,
                            "demo": True
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {
                    "example": {"detail": "Text too short for meaningful analysis (minimum 50 characters)"}
                }
            }
        }
    }
}


# Plagiarism endpoint examples
PLAGIARISM_RESPONSES = {
    "check": {
        200: {
            "description": "Plagiarism check result",
            "content": {
                "application/json": {
                    "example": {
                        "similarity_score": 0.12,
                        "is_potentially_plagiarized": False,
                        "threshold": 0.5,
                        "similar_documents": [],
                        "analysis_id": 42,
                        "checked_at": "2026-01-03T14:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {
                    "example": {"detail": "Text too short for plagiarism check (minimum 100 characters)"}
                }
            }
        }
    },
    "stats": {
        200: {
            "description": "Plagiarism detection statistics",
            "content": {
                "application/json": {
                    "example": {
                        "total_documents": 1542,
                        "total_checks": 3891,
                        "flagged_documents": 23,
                        "average_similarity": 0.08
                    }
                }
            }
        }
    }
}


# Reviewer endpoint examples
REVIEWER_RESPONSES = {
    "create": {
        201: {
            "description": "Reviewer profile created",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "user_id": 5,
                        "username": "dr_smith",
                        "email": "smith@university.edu",
                        "expertise_keywords": ["machine learning", "computer vision", "deep learning"],
                        "expertise_description": "Expert in ML and CV with 10 years of research experience",
                        "institution": "Stanford University",
                        "department": "Computer Science",
                        "orcid_id": "0000-0001-2345-6789",
                        "is_available": True,
                        "current_assignments": 0,
                        "max_assignments": 5,
                        "available_slots": 5,
                        "created_at": "2026-01-03T10:00:00Z",
                        "updated_at": "2026-01-03T10:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Profile creation failed",
            "content": {
                "application/json": {
                    "example": {"detail": "User already has a reviewer profile"}
                }
            }
        }
    },
    "list": {
        200: {
            "description": "List of reviewers",
            "content": {
                "application/json": {
                    "example": {
                        "reviewers": [
                            {
                                "id": 1,
                                "username": "dr_smith",
                                "expertise_keywords": ["machine learning", "computer vision"],
                                "institution": "Stanford University",
                                "is_available": True,
                                "available_slots": 3
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "page_size": 20,
                            "total_count": 45,
                            "total_pages": 3
                        }
                    }
                }
            }
        }
    },
    "suggest": {
        200: {
            "description": "Reviewer suggestions for manuscript",
            "content": {
                "application/json": {
                    "example": {
                        "analysis_id": 42,
                        "suggestions": [
                            {
                                "reviewer_id": 1,
                                "username": "dr_smith",
                                "match_score": 0.89,
                                "matched_keywords": ["machine learning", "neural networks"],
                                "institution": "Stanford University",
                                "available_slots": 3
                            },
                            {
                                "reviewer_id": 7,
                                "username": "prof_jones",
                                "match_score": 0.76,
                                "matched_keywords": ["deep learning"],
                                "institution": "MIT",
                                "available_slots": 2
                            }
                        ],
                        "total_matches": 2
                    }
                }
            }
        }
    }
}


# Common responses for all authenticated endpoints
COMMON_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    429: RATE_LIMIT_RESPONSE,
    500: SERVER_ERROR_RESPONSE
}
