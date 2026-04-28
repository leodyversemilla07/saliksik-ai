# Saliksik AI

**AI-powered manuscript pre-review system for Research Journal Management**

[![CI](https://github.com/leodyversemilla07/saliksik-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/leodyversemilla07/saliksik-ai/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.127-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Saliksik AI streamlines the initial manuscript review process by automatically analyzing submitted manuscripts, providing editors and reviewers with instant insights on content quality, readability, and key themes before formal peer review begins.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [Development](#development)
- [License](#license)

---

## Features

### Core Capabilities

- **AI-Powered Summarization** — DistilBART transformer model for abstractive summarization (306M params, ~600MB)
- **Keyword Extraction** — YAKE algorithm for unsupervised keyword identification, no training data needed
- **Readability Scoring** — Flesch Reading Ease, Flesch-Kincaid Grade, Automated Readability Index via textstat
- **Plagiarism Detection** — MinHash LSH for efficient document similarity checking
- **Reviewer Matching** — Semantic similarity matching using sentence-transformers (all-MiniLM-L6-v2)
- **PDF Support** — Direct PDF upload with text extraction via pypdf
- **Smart Caching** — Redis-backed caching with in-memory fallback and auto-eviction
- **User Management** — JWT auth with access/refresh token rotation, API keys, RBAC, account lockout

### Technical Features

- **Async Everything** — FastAPI + async SQLAlchemy + Celery task queue
- **Auto-Generated Docs** — Interactive Swagger UI and ReDoc at `/docs`
- **Docker Ready** — Docker Compose with PostgreSQL, Redis, and health checks
- **CI/CD** — GitHub Actions with linting (ruff) and test coverage (pytest-cov)
- **Security** — Hardened SECRET_KEY validation, input sanitization, rate limiting, security headers

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API Framework | FastAPI 0.127 | Async, auto-docs, type-safe |
| Database | PostgreSQL 15 + asyncpg | ACID, connection pooling |
| Cache | Redis 7 | Low-latency caching + Celery broker |
| Auth | python-jose + bcrypt | JWT with token rotation |
| Summarization | DistilBART (sshleifer/distilbart-cnn-12-6) | 27% smaller than BART, near-identical quality |
| Keywords | YAKE | Unsupervised, no training data, multilingual-ready |
| Readability | textstat | Pure Python, accurate Flesch scores, no Java needed |
| Plagiarism | datasketch (MinHash LSH) | O(n) similarity, scales to large corpora |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 22.7M params, fast, good for semantic search |
| Background Tasks | Celery + Redis | Async manuscript processing |
| Testing | pytest + pytest-asyncio + httpx | 80+ tests, async test client |
| Linting | ruff | Fast, replaces flake8 + black + isort |

### Why these models?

The ML stack was chosen to maximize quality per megabyte. BART-large-cnn (1.5GB) was replaced with DistilBART (600MB) for nearly identical summarization quality. language-tool-python (requires Java JRE) was replaced with textstat (pure Python). TF-IDF was replaced with YAKE for better academic keyword extraction without scikit-learn.

---

## Quick Start

### Using Docker (Recommended)

```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai

# Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY and POSTGRES_PASSWORD

# Start all services
docker-compose up -d --build

# Access:
# - Swagger UI:  http://localhost:8000/docs
# - ReDoc:       http://localhost:8000/redoc
# - Health:      http://localhost:8000/health
```

### Manual Setup (using uv)

> **Prerequisite:** Install uv from https://docs.astral.sh/uv/getting-started/installation/

```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai

# Create virtual environment with uv
uv venv

# Install all dependencies (main + test + dev) in editable mode
uv pip install -e ".[test,dev]"

# Download NLP models
uv run python -m spacy download en_core_web_sm
uv run python -c "import nltk; nltk.download('punkt')"

# Configure
cp .env.example .env  # Windows: copy .env.example .env
# Edit .env with your database credentials and SECRET_KEY

# Start server (editable install makes `app` importable automatically)
uv run uvicorn main:app --reload
```

---

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (optional, falls back to in-memory cache)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Min 32 chars. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DATABASE_URL` | Yes | Async DB URL: `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `REDIS_URL` | No | Redis URL for caching. Falls back to in-memory if not set. |
| `DEBUG` | No | Set `true` for development. Default: `false` |

---

## Usage

### Basic Workflow

1. **Register & Login** — Get a JWT token via `/api/v1/auth/register` and `/api/v1/auth/login`

2. **Submit Manuscript** — Send text or PDF to `/api/v1/analysis/pre-review`

3. **View Results** — Poll `/api/v1/analysis/status/{task_id}` for the analysis report

### Key Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/register` | POST | No | Create account |
| `/api/v1/auth/login` | POST | No | Get JWT tokens |
| `/api/v1/analysis/pre-review` | POST | Yes | Submit manuscript for analysis |
| `/api/v1/analysis/demo` | POST | No | Public demo (5000 char limit) |
| `/api/v1/analysis/history` | GET | Yes | View past analyses |
| `/api/v1/plagiarism/check` | POST | Yes | Check for plagiarism |
| `/api/v1/reviewers/suggest` | POST | Yes | Get reviewer suggestions |
| `/health` | GET | No | System health check |

For full API documentation, see [docs/API_REFERENCE.md](docs/API_REFERENCE.md) or the interactive Swagger UI at `/docs`.

---

## Architecture

```
saliksik-ai/
├── app/
│   ├── api/v1/           # Route handlers (auth, analysis, plagiarism, reviewers)
│   ├── core/             # Config, DB, security, cache, rate limiting, utils
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic (AI, plagiarism, citations, reviewers)
│   ├── tasks/            # Celery background tasks
│   └── utils/            # Utilities (migrations)
├── alembic/              # Database migrations
├── docs/                 # Project documentation
├── tests/                # Test suite (80+ tests)
├── .github/workflows/    # CI pipeline
├── main.py               # FastAPI entry point
├── pyproject.toml        # Project metadata and dependencies
├── docker-compose.yml    # Full stack orchestration
└── pytest.ini            # Test configuration
```

### Request Flow

```
Client → FastAPI (auth + validation) → Celery Task (async)
                                          ↓
                              AI Pipeline (summarize + keywords + quality)
                                          ↓
                              PostgreSQL (store results) → Redis (cache)
                                          ↓
Client ← API Response (poll status endpoint)
```

---

## Development

### Running Tests

```bash
# Run all tests with coverage (editable install makes app importable)
uv run pytest

# Run specific test file
uv run pytest tests/test_cache.py

# Run with verbose output
uv run pytest -v
```

### Linting & Type Checking

```bash
# Lint and auto-fix issues
uv run ruff check --fix app/

# Format code
uv run ruff format app/

# Type check with ty (fast, written in Rust)
uv run ty check app/

# Or run all checks together
uv run ruff check app/ && uv run ty check app/
```

### CI Pipeline

The GitHub Actions workflow runs on every push to `main`:
- **Lint job** — ruff check + format verification
- **Test job** — pytest with coverage, PostgreSQL + Redis services

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Leodyver S. Semilla
