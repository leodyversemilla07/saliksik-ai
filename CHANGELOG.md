# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Docker containerization with Docker Compose orchestration
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
