# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- A bundled web interface: a landing page at `/` and a dashboard at `/dashboard` with
  registration, login, manuscript submission (text or PDF), live status polling, analysis
  history, reviewer profile management, citation analysis and plagiarism checks. The
  `static/` directory was ignored by a leftover Django rule in `.gitignore`, so the pages
  were missing from every clone.
- Administration API: `GET /api/v1/admin/stats`, `GET /api/v1/admin/users`,
  `GET /api/v1/admin/users/{id}` and `PATCH /api/v1/admin/users/{id}` for listing
  accounts, changing roles and deactivating users. An administrator cannot remove
  their own admin role or deactivate their own account.
- `scripts/create_admin.py` creates or promotes the first administrator.
- Password reset flow: `POST /api/v1/auth/forgot-password` and
  `POST /api/v1/auth/reset-password` with single-use, expiring tokens. The request
  endpoint returns the same response for known and unknown addresses so it cannot be
  used to enumerate users.

### Security
- Fixed API-key authentication: the strict OAuth2 scheme rejected requests without an
  `Authorization` header before the API key was looked at, so the documented `X-API-Key`
  flow never worked. Endpoints that accept either credential now use an optional scheme.
- Access tokens can no longer be minted from a refresh token: `decode_access_token()` now
  requires `type == "access"`.
- Every issued token carries a `jti`, and access-token decoding honours the blacklist, so
  logout actually revokes the access token.
- Inactive users can no longer log in, and previously issued tokens stop working once the
  account is deactivated (JWT and API-key paths).
- Passwords are SHA-256 pre-hashed before bcrypt, so passwords longer than bcrypt's 72-byte
  limit no longer raise `ValueError`; legacy raw bcrypt hashes stay verifiable.
- `SECRET_KEY` is validated at startup (minimum 32 characters, minimum 8 distinct characters,
  example placeholder rejected).
- HTTP error responses keep their protocol headers (`WWW-Authenticate`, `Retry-After`).
- Request IDs are sanitised and sensitive query parameters (`token`, `password`, `secret`,
  `api_key`, `apikey`, `code`) are redacted from the request logs.
- Plagiarism comparisons are scoped to the requesting user's own documents.
- Dependency upgrades: FastAPI 0.162, Starlette 1.10, PyJWT 2.15 (replaces `python-jose`),
  pypdf 6.21, python-multipart 0.0.32, sentence-transformers 5.6, torch 2.14, cryptography 50.
  Known advisories dropped from 266 (21 packages) to 10 (transformers 4.x only).

### Fixed
- The request size limit middleware returned `500` for oversized uploads and invalid
  `Content-Length` headers (it raised an `HTTPException` outside the exception handlers); it
  now returns `400`/`413` with the standard error envelope.
- The language detector now honours the configured `SUPPORTED_LANGUAGES` list instead of
  ignoring it.
- Manuscripts are no longer truncated to 10,000 characters; the limit is now an explicit
  `MAX_MANUSCRIPT_CHARS` (200,000) and oversized submissions return `413`.
- The Celery task receives only the analysis id — manuscript text is no longer copied into the
  broker message or the result metadata (`result_extended=False`).
- The plagiarism threshold from the request (or `PLAGIARISM_THRESHOLD`) is honoured, and the
  detector compares with `>=` instead of the previous hard-coded value.
- Language detection, citation analysis and plagiarism results are produced by the background
  task and persisted (`language_info`, `plagiarism_result`); the analysis response exposes
  `language`, `plagiarism` and `citation_analysis`.
- Document fingerprints are created for every successful analysis and used to rebuild the
  plagiarism index.
- Reviewer suggestions no longer trigger an async lazy load (`MissingGreenlet`): reviewer
  profiles are eager-loaded with `selectinload`.
- The manuscript embedding is computed once per matching request instead of once per reviewer.
- The manuscript author can no longer be assigned as a reviewer of their own manuscript, and
  reviewer-assignment status transitions are validated.
- ORCID identifiers are validated against the ISO 7064 checksum format.
- The demo endpoint reports the detected language and citation analysis.
- Stale analyses are marked as failed by a scheduled Celery Beat task.
- Rate-limit responses use the standard error envelope.
- The health endpoint returns `503` when the database is unreachable and no longer leaks a Redis
  connection per request.
- `X-Forwarded-For` is only trusted when the direct peer is listed in `TRUSTED_PROXIES`.
- The cache invalidation uses `SCAN` instead of `KEYS`, so it no longer blocks Redis.
- Model inference (summarisation, embeddings, citation parsing) runs in a worker thread instead
  of blocking the event loop.
- `LOG_LEVEL` and `CELERY_TASK_ALWAYS_EAGER` are now honoured by the logging setup and the Celery
  configuration.
- Removed the unused `app/utils/migration.py` helper.
- The test suite no longer hangs at exit (the async test engine is disposed) and uses a
  process-unique SQLite file so parallel runs cannot collide.

### Changed
- Readability metrics (Flesch Reading Ease, Flesch-Kincaid, ARI) are computed locally with
  `pyphen` and a regex sentence splitter; `textstat` and `nltk` were removed because they could
  not be imported reliably in the locked environment.
- `pypdf` is imported lazily so PDF support does not slow down application startup.
- CI now runs `pip-audit` and an Alembic migration/schema-drift check in addition to linting
  and tests.

### Added
- `POST /api/v1/citations/analyze` for on-demand citation analysis (style detection, reference
  parsing, in-text cross-check, issue reporting).
- Multi-language analysis: the NLP model manager is used by the pre-review service, the detected
  language selects the spaCy pipeline, and the worker switches the pipeline per manuscript.
- `PUT /api/v1/auth/profile` to set the account affiliation, and an optional `institution`
  field on registration and in the user response.
- Reviewer assignments now fail with `409 Conflict` when the reviewer shares the author's
  institution, and such reviewers are filtered out of the suggestions.
- Reviewers that reached their assignment limit are no longer suggested.
- Shared OpenAPI response documentation (`app/api/responses.py`) that describes the real error
  envelope; the module is now used by every router.
- Contract tests for the analysis history/cache endpoints, the reviewer profile workflow, the
  API key lifecycle, token refresh and password changes.
- Tests for the request size limit middleware and the language detector configuration.
- Regression tests for authentication, token revocation, password handling, secret validation,
  error headers, log hygiene, plagiarism thresholds/tenant isolation and reviewer matching.
- Alembic revision `007_analysis_enhancements` adding the `language_info` and
  `plagiarism_result` columns.
- Alembic revision `008_user_institution` adding the author affiliation used for reviewer
  conflict-of-interest checks.

## [2.1.0] - 2025-12-22

### Added

#### Plagiarism Detection
- MinHash LSH algorithm for efficient document similarity checking
- Document fingerprinting using xxhash for fast hashing
- Configurable similarity threshold (default: 0.5)
- New endpoints:
  - `POST /api/v1/plagiarism/check` - Check manuscript for plagiarism
  - `GET /api/v1/plagiarism/stats` - Get index statistics
  - `POST /api/v1/plagiarism/index/rebuild` - Rebuild document index

#### Citation Analysis
- Automatic citation format detection (APA, MLA, IEEE, Chicago)
- Reference section extraction and parsing
- In-text citation extraction and validation
- Cross-validation between references and in-text citations
- Format consistency scoring
- Outdated reference detection (>10 years)
- New `citation_analysis` field in analysis response

#### Reviewer Matching
- Semantic similarity matching using sentence-transformers (all-MiniLM-L6-v2)
- Keyword-based matching with TF-IDF
- Hybrid scoring combining keyword and semantic similarity
- Reviewer availability and workload tracking
- Assignment management workflow (suggested → invited → accepted/declined → completed)
- Conflict of interest checking
- New endpoints:
  - `POST /api/v1/reviewers/` - Create reviewer profile
  - `GET /api/v1/reviewers/me` - Get own profile
  - `PUT /api/v1/reviewers/me` - Update own profile
  - `GET /api/v1/reviewers/` - List all reviewers
  - `GET /api/v1/reviewers/analysis/{id}/suggestions` - Get reviewer suggestions
  - `POST /api/v1/reviewers/analysis/{id}/assign/{rid}` - Assign reviewer
  - `GET /api/v1/reviewers/my-assignments` - Get my assignments
  - `PUT /api/v1/reviewers/assignments/{id}/status` - Update assignment status

#### Multi-Language Support
- Automatic language detection using langdetect
- Support for 12 languages: English, Spanish, French, German, Portuguese, Italian, Dutch, Chinese, Japanese, Korean, Russian, Arabic
- Lazy loading of spaCy models per language
- Language confidence scoring
- New `language` field in analysis response with detected language info

### Changed
- Updated `app/core/config.py` with feature flags for all new features
- Updated `app/schemas/analysis.py` with new response fields
- Updated `app/models/analysis.py` with relationships for new features
- Updated `app/api/v1/info.py` to expose new feature information

### Dependencies
- Added `datasketch>=1.6.0` for MinHash LSH plagiarism detection
- Added `xxhash>=3.4.0` for fast document fingerprinting
- Added `sentence-transformers>=2.2.0` for semantic similarity
- Added `langdetect>=1.0.9` for language detection

## [2.0.0] - 2025-12-01

### Added
- Core manuscript pre-review functionality
- AI-powered summarization using BART transformer model
- TF-IDF based keyword extraction
- Language quality analysis with grammar checking and readability scoring
- PDF manuscript upload with text extraction
- Redis-based caching with 40-100x speedup on repeated queries
- JWT-based authentication for editorial staff and reviewers
- Async processing with Celery task queue
- PostgreSQL database with connection pooling and indexing
- Rate limiting and input validation
- Structured logging with request ID tracking

### Endpoints
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User authentication
- `POST /api/v1/analysis/pre-review` - Submit manuscript for analysis
- `GET /api/v1/analysis/{id}` - Get analysis results
- `GET /health` - Health check endpoint

## [1.0.0] - 2025-11-01

### Added
- Initial project setup
- Basic FastAPI application structure
- Database models and migrations
- Authentication system

---

**Project Repository**: [GitHub](https://github.com/leodyversemilla07/saliksik-ai)
