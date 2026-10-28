# API Reference

Complete API documentation for Saliksik AI

## Base URL

```
http://localhost:8000
```

## Authentication

All protected endpoints require JWT authentication:

```http
Authorization: Bearer <your_jwt_token>
```

Get your token by logging in through `/api/v1/auth/login`.

---

## Authentication Endpoints

### Register User

Create a new user account.

**Endpoint:** `POST /api/v1/auth/register`

**Authentication:** Not required

**Request Body:**
```json
{
 "username": "string (3-50 chars, required)",
 "email": "string (valid email, required)",
 "password": "string (min 8 chars, required)"
}
```

**Response:** `201 Created`
```json
{
 "access_token": "string",
 "token_type": "bearer",
 "user": {
 "id": 1,
 "username": "editor1",
 "email": "editor@journal.com",
 "is_active": true,
 "created_at": "2025-11-07T08:22:54Z",
 "last_login": null
 }
}
```

**Error Responses:**
- `400 Bad Request` - Username or email already exists
- `400 Bad Request` - Validation error (password too short, invalid email, etc.)

---

### Login

Authenticate and get JWT access token.

**Endpoint:** `POST /api/v1/auth/login`

**Authentication:** Not required

**Request Body:**
```json
{
 "username": "string (required)",
 "password": "string (required)"
}
```

**Response:** `200 OK`
```json
{
 "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
 "token_type": "bearer",
 "user": {
 "id": 1,
 "username": "editor1",
 "email": "editor@journal.com",
 "is_active": true,
 "created_at": "2025-11-07T08:22:54Z",
 "last_login": "2025-11-07T08:30:00Z"
 }
}
```

**Error Responses:**
- `401 Unauthorized` - Incorrect username or password

---

### Get Profile

Get current user's profile information.

**Endpoint:** `GET /api/v1/auth/profile`

**Authentication:** Required

**Response:** `200 OK`
```json
{
 "id": 1,
 "username": "editor1",
 "email": "editor@journal.com",
 "role": "user",
 "institution": "Example University",
 "is_active": true,
 "is_email_verified": true,
 "created_at": "2025-11-07T08:22:54Z",
 "last_login": "2025-11-07T08:30:00Z"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or expired token

---

### Update Profile

Update the current user's affiliation. The affiliation is used to detect
reviewer conflicts of interest: a reviewer from the same institution is neither
suggested nor assignable.

**Endpoint:** `PUT /api/v1/auth/profile`

**Authentication:** Required

**Request Body:**
```json
{
 "institution": "Example University"
}
```

**Response:** `200 OK` — the updated user object.

**Error Responses:**
- `401 Unauthorized` - Invalid or expired token
- `422 Unprocessable Entity` - Invalid payload

---

## Analysis Endpoints

### Demo Analysis

Public endpoint for testing (no authentication required).

**Endpoint:** `POST /api/v1/analysis/demo`

**Authentication:** Not required

**Request Body (Text):**
```json
{
 "manuscript_text": "string (50-5000 chars, required)"
}
```

**Response:** `200 OK`
```json
{
 "summary": "AI-generated summary of the manuscript...",
 "keywords": [
 "keyword1",
 "keyword2",
 "keyword3"
 ],
 "language_quality": {
 "word_count": 350,
 "unique_words": 220,
 "sentence_count": 15,
 "named_entities": 5,
 "readability_score": 65.4,
 "grammar_issues": 2,
 "grammar_check_available": true
 },
 "metadata": {
 "input_length": 350,
 "processing_time": 1.23,
 "cached": false,
 "demo": true
 }
}
```

**Error Responses:**
- `400 Bad Request` - Text too short (< 50 chars)
- `400 Bad Request` - Text too long (> 5000 chars for demo)
- `500 Internal Server Error` - Processing error

---

### Full Manuscript Analysis

Analyze manuscript (text or PDF) with full features.

**Endpoint:** `POST /api/v1/analysis/pre-review`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

**Request Parameters:**

Either:
- `manuscript_text` (form field): Text content (50 chars to `MAX_MANUSCRIPT_CHARS`, default 200,000)

Or:
- `manuscript_file` (file upload): PDF file (max `MAX_FILE_SIZE_MB`, default 50MB)

**Response:** `202 Accepted`
```json
{
 "task_id": "b9dfbcd9-fd59-4bab-8fb7-586ca10e487a",
 "analysis_id": 123,
 "status": "PENDING",
 "message": "Analysis started successfully. Poll /status/{task_id} for results."
}
```

The submission is asynchronous: poll `GET /api/v1/analysis/status/{task_id}` for the result.
Only the analysis id is sent to the queue — the manuscript text stays in the database.

**Error Responses:**
- `400 Bad Request` - No text or file provided
- `400 Bad Request` - Invalid file type (PDF only)
- `400 Bad Request` - File too large (> `MAX_FILE_SIZE_MB`)
- `400 Bad Request` - Text too short (< 50 chars)
- `401 Unauthorized` - Invalid or missing token
- `413 Request Entity Too Large` - Text longer than `MAX_MANUSCRIPT_CHARS`
- `503 Service Unavailable` - The analysis queue could not be reached

---

### Analysis Status

Poll a background analysis using the `task_id` returned by `POST /api/v1/analysis/pre-review`.

**Endpoint:** `GET /api/v1/analysis/status/{task_id}`

**Authentication:** Required

While the task is queued or running, the response contains a `status` field:

```json
{
 "task_id": "abc123-def456",
 "status": "PENDING",
 "message": "Analysis in progress..."
}
```

When the task completes, the response is the full analysis result (the same shape as the demo response), including `summary`, `keywords`, `language_quality`, `metadata`, and — when the corresponding features are enabled — `language`, `plagiarism` and `citation_analysis`. If the task failed, the response contains `"status": "FAILED"`.

---

### Analysis History

Get paginated history of user's analyses.

**Endpoint:** `GET /api/v1/analysis/history`

**Authentication:** Required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (default: 20, max: 100)

**Response:** `200 OK`
```json
{
 "results": [
 {
 "id": 123,
 "filename": "manuscript.pdf",
 "input_type": "pdf",
 "word_count": 1250,
 "readability_score": 68.5,
 "created_at": "2025-11-07T08:22:54Z",
 "processing_time": 2.34
 }
 ],
 "pagination": {
 "page": 1,
 "page_size": 20,
 "total_count": 45,
 "total_pages": 3,
 "has_next": true,
 "has_previous": false
 }
}
```

---

### Cache Statistics

Get cache performance statistics.

**Endpoint:** `GET /api/v1/analysis/cache/stats`

**Authentication:** Required (admin only)

**Response:** `200 OK`
```json
{
 "cache": {
 "backend": "redis",
 "enabled": true,
 "keyspace_hits": 1500,
 "keyspace_misses": 250,
 "hit_rate": 85.71
 },
 "message": "Cache statistics retrieved successfully"
}
```

---

### Clear Cache

Clear all cached analysis results.

**Endpoint:** `POST /api/v1/analysis/cache/clear`

**Authentication:** Required (admin only)

**Response:** `200 OK`
```json
{
 "message": "Cache cleared successfully",
 "cleared_by": "editor1"
}
```

---

## System Endpoints

### Health Check

Check if the API is running.

**Endpoint:** `GET /health`

**Authentication:** Not required

**Response:** `200 OK`
```json
{
 "status": "healthy",
 "version": "2.0.0",
 "environment": "development"
}
```

---

### API Information

Get API metadata and capabilities.

**Endpoint:** `GET /api/v1/info`

**Authentication:** Not required

**Response:** `200 OK`
```json
{
 "name": "Saliksik AI",
 "version": "2.0.0",
 "description": "AI-powered manuscript pre-review system...",
 "features": [
 "AI-powered summarization using BART model",
 "Keyword extraction with TF-IDF",
 "Language quality analysis",
 "PDF text extraction",
 "JWT-based authentication",
 "Redis caching for performance",
 "Rate limiting and security controls"
 ],
 "endpoints": {
 "docs": "/docs - Interactive API documentation (Swagger UI)",
 "redoc": "/redoc - Alternative API documentation (ReDoc)",
 "health": "/health - Health check endpoint",
 "api_info": "/api/v1/info - This endpoint"
 },
 "limits": {
 "demo_max_text_length": 5000,
 "authenticated_max_text_length": 200000,
 "max_file_size_mb": 50,
 "plagiarism_threshold": 0.5
 },
 "features_enabled": {
 "plagiarism_check": true,
 "citation_analysis": true,
 "reviewer_matching": true,
 "auto_detect_language": true
 },
 "status": {
 "server": "online",
 "debug_mode": false,
 "cache_backend": "redis"
 }
}
```

---

## Error Responses

All endpoints may return the following error formats:

### Validation Error

**Status:** `422 Unprocessable Entity`

```json
{
 "error": {
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
   "errors": [
    {
     "field": "body.manuscript_text",
     "message": "Field required",
     "type": "missing"
    }
   ]
  }
 }
}
```

### Authentication Error

**Status:** `401 Unauthorized`

```json
{
 "error": {
  "code": "HTTP_ERROR",
  "message": "Invalid or expired token"
 }
}
```

The response also carries the `WWW-Authenticate: Bearer` header.

### Not Found

**Status:** `404 Not Found`

```json
{
 "error": {
  "code": "HTTP_ERROR",
  "message": "Not Found"
 }
}
```

### Server Error

**Status:** `500 Internal Server Error`

```json
{
 "error": {
  "code": "INTERNAL_ERROR",
  "message": "An unexpected error occurred"
 }
}
```

### Rate Limit

**Status:** `429 Too Many Requests`

```json
{
 "error": {
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Try again in 60 seconds."
 }
}
```

The response carries a `Retry-After` header.

---

## Plagiarism Detection Endpoints

### Check Plagiarism

Check manuscript for plagiarism against stored documents.

**Endpoint:** `POST /api/v1/plagiarism/check`

**Authentication:** Required

**Request Body:**
```json
{
 "manuscript_text": "string (50-100000 chars, required)",
 "threshold": 0.5  // Optional, 0.1-0.95; defaults to PLAGIARISM_THRESHOLD
}
```

The comparison is scoped to the authenticated user's own documents.

**Response:** `200 OK`
```json
{
 "is_plagiarized": false,
 "overall_similarity": 0.15,
 "similar_documents": [
  {
   "analysis_id": 45,
   "similarity_score": 0.15,
   "matched_segments": ["sample matching text..."],
   "original_filename": "previous_paper.pdf"
  }
 ],
 "unique_content_percentage": 85.0,
 "processing_time": 0.234,
 "checked_against": 42
}
```

---

### Get Plagiarism Stats

Get plagiarism detection index statistics.

**Endpoint:** `GET /api/v1/plagiarism/stats`

**Authentication:** Required

**Response:** `200 OK`
```json
{
 "documents_indexed": 150,
 "threshold": 0.5,
 "num_permutations": 128,
 "shingle_size": 5,
 "datasketch_available": true,
 "xxhash_available": true
}
```

---

## Reviewer Matching Endpoints

### Create Reviewer Profile

Create a reviewer profile for the current user.

**Endpoint:** `POST /api/v1/reviewers/`

**Authentication:** Required

**Request Body:**
```json
{
 "expertise_keywords": ["machine learning", "natural language processing"],
 "expertise_description": "10 years experience in NLP research",
 "institution": "University of Science",
 "department": "Computer Science",
 "orcid_id": "0000-0001-2345-6789",
 "max_assignments": 5
}
```

**Response:** `201 Created`
```json
{
 "id": 1,
 "user_id": 5,
 "username": "reviewer1",
 "email": "reviewer@university.edu",
 "expertise_keywords": ["machine learning", "natural language processing"],
 "is_available": true,
 "current_assignments": 0,
 "max_assignments": 5,
 "available_slots": 5
}
```

---

### Get Reviewer Suggestions

Get AI-powered reviewer suggestions for a manuscript.

**Endpoint:** `GET /api/v1/reviewers/analysis/{analysis_id}/suggestions`

**Authentication:** Required

**Query Parameters:**
- `top_n` (integer, optional): Max suggestions (1-20, default: 5)
- `min_score` (float, optional): Min match score (0.0-1.0, default: 0.1)

**Response:** `200 OK`
```json
{
 "analysis_id": 123,
 "manuscript_keywords": ["machine learning", "classification"],
 "suggestions": [
  {
   "reviewer_id": 1,
   "user_id": 5,
   "username": "expert_reviewer",
   "match_score": 0.85,
   "matched_keywords": ["machine learning"],
   "match_method": "hybrid",
   "institution": "MIT",
   "available_slots": 3
  }
 ],
 "total_available_reviewers": 15
}
```

---

### Assign Reviewer

Assign a reviewer to a manuscript analysis.

**Endpoint:** `POST /api/v1/reviewers/analysis/{analysis_id}/assign/{reviewer_id}`

**Authentication:** Required

**Request Body:**
```json
{
 "send_invitation": true,
 "message": "Please review this manuscript on ML techniques."
}
```

**Response:** `200 OK`
```json
{
 "id": 1,
 "analysis_id": 123,
 "reviewer_id": 5,
 "reviewer_username": "expert_reviewer",
 "match_score": 0.85,
 "matched_keywords": ["machine learning"],
 "status": "invited",
 "created_at": "2025-12-22T10:00:00Z",
 "invited_at": "2025-12-22T10:00:00Z"
}
```

---

### List Reviewers

List all available reviewers.

**Endpoint:** `GET /api/v1/reviewers/`

**Authentication:** Required

**Query Parameters:**
- `page` (integer, optional): Page number (default: 1)
- `page_size` (integer, optional): Items per page (1-100, default: 20)
- `available_only` (boolean, optional): Only show available reviewers
- `keyword` (string, optional): Filter by expertise keyword

---

## Enhanced Analysis Response

The analysis response now includes additional enhancement fields:

```json
{
 "summary": "AI-generated summary...",
 "keywords": ["keyword1", "keyword2"],
 "language_quality": {
  "word_count": 1250,
  "readability_score": 68.5
 },
 "metadata": {...},
 "language": {
  "code": "en",
  "name": "English",
  "confidence": 0.98
 },
 "plagiarism": {
  "is_plagiarized": false,
  "overall_similarity": 0.12
 },
 "citation_analysis": {
  "total_citations": 25,
  "format_detected": "apa",
  "format_consistency": 92.0
 }
}
```

---

## Rate Limiting

- **Anonymous users**: 60 requests/hour
- **Authenticated users**: 100 requests/hour

When rate limit is exceeded:

**Status:** `429 Too Many Requests`

```json
{
 "detail": "Rate limit exceeded"
}
```

---

## Interactive Documentation

For the best API exploration experience, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Both provide:
- Interactive request testing
- Detailed schema documentation
- Authentication testing
- Example requests and responses
