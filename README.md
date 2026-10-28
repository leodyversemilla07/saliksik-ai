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
- **Readability Scoring** — Flesch Reading Ease, Flesch-Kincaid Grade and Automated Readability Index (local, no external services)
- **Plagiarism Detection** — MinHash LSH for efficient document similarity checking
- **Reviewer Matching** — Semantic similarity matching using sentence-transformers (all-MiniLM-L6-v2)
- **PDF Support** — Direct PDF upload with text extraction via pypdf
- **Smart Caching** — Redis-backed caching with in-memory fallback and auto-eviction
- **User Management** — JWT auth with access/refresh token rotation, API keys, RBAC, account lockout

### Technical Features

- **Async Everything** — FastAPI + async SQLAlchemy + Celery task queue
- **Auto-Generated Docs** — Interactive Swagger UI and ReDoc at `/docs`
- **CI/CD** — GitHub Actions with linting (ruff) and test coverage (pytest-cov)
- **Security** — Hardened SECRET_KEY validation, input sanitization, rate limiting, security headers

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API Framework | FastAPI 0.162 | Async, auto-docs, type-safe |
| Database | PostgreSQL 15 + asyncpg | ACID, connection pooling |
| Cache | Redis 7 | Low-latency caching + Celery broker |
| Auth | PyJWT + bcrypt | JWT with token rotation and token-type separation |
| Summarization | DistilBART (sshleifer/distilbart-cnn-12-6) | 27% smaller than BART, near-identical quality |
| Keywords | YAKE | Unsupervised, no training data, multilingual-ready |
| Readability | pyphen | Local syllable hyphenation for Flesch/FK/ARI, no Java or NLTK data needed |
| Plagiarism | datasketch (MinHash LSH) | O(n) similarity, scales to large corpora |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 22.7M params, fast, good for semantic search |
| Background Tasks | Celery + Redis | Async manuscript processing |
| Testing | pytest + pytest-asyncio + httpx | 130+ tests, async test client |
| Linting | ruff | Fast, replaces flake8 + black + isort |

### Why these models?

The ML stack was chosen to maximize quality per megabyte. BART-large-cnn (1.5GB) was replaced with DistilBART (600MB) for nearly identical summarization quality. language-tool-python (requires Java JRE) was replaced with a local readability implementation built on `pyphen`. TF-IDF was replaced with YAKE for better academic keyword extraction without scikit-learn.

---

## Quick Start

### Using uv (Recommended)

> **Prerequisites:** Python 3.12+, PostgreSQL 15+, Redis 7+, and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai

# Create virtual environment with uv
uv venv

# Install all dependencies (main + test + dev) in editable mode
uv pip install -e ".[test,dev]"

# Configure
cp .env.example .env  # Windows: copy .env.example .env
# Edit .env with your database URL and SECRET_KEY

# Apply database migrations
uv run alembic upgrade head

# Terminal 1 — start the API
uv run uvicorn main:app --reload
```

Then start the Celery worker in a second terminal (required for manuscript analysis):

```bash
uv run celery -A app.celery_app.celery_app worker --loglevel=INFO --queues=analysis,default
```

Celery Beat is optional but recommended — it runs the periodic cleanup of stale analyses:

```bash
uv run celery -A app.celery_app.celery_app beat --loglevel=INFO
```

On the first analysis, the DistilBART summarization model (~600 MB) is downloaded from Hugging Face and
cached under `~/.cache/huggingface`. For a faster, lower-memory setup that skips the transformer, set
`AI_LIGHT_MODE=True` in `.env`.

### Local PostgreSQL and Redis (no Docker, no sudo)

If PostgreSQL and Redis are not installed system-wide, use the local service helper:

```bash
./scripts/local-services.sh setup   # one-time: install pgserver + redislite in a user venv
./scripts/local-services.sh up      # start PostgreSQL + Redis and create the dev database
./scripts/local-services.sh status  # show service status
./scripts/local-services.sh down    # stop both services
```

The helper installs binaries under `~/.local/share/saliksik-ai/services-venv`, stores data in
`~/.local/share/saliksik-ai/{postgres,redis}`, and listens on `127.0.0.1:5432` (PostgreSQL) and
`127.0.0.1:6379` (Redis). It also creates the `saliksik` role (password `saliksik123`) and
`saliksik_ai_dev` database used by the quick-start `.env`.

These services are unprivileged and do not start automatically after a reboot. Run
`./scripts/local-services.sh up` before starting the API and Celery worker.

Access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

---

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (required for background analysis; optional for caching)

> No Docker or sudo access? The [local service helper](#local-postgresql-and-redis-no-docker-no-sudo)
> installs unprivileged PostgreSQL and Redis binaries in your home directory.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Min 32 chars. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DATABASE_URL` | Yes | Async DB URL: `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `REDIS_URL` | No | Redis URL for caching. Falls back to in-memory if not set. |
| `CELERY_BROKER_URL` | No | Redis broker for Celery. Defaults to `redis://localhost:6379/1`. |
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
| `/api/v1/citations/analyze` | POST | Yes | Analyse citations and references |
| `/api/v1/reviewers/analysis/{id}/suggestions` | GET | Yes | Get reviewer suggestions |
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
│   └── tasks/            # Celery background tasks
├── alembic/              # Database migrations
├── docs/                 # Project documentation
├── tests/                # Test suite (130+ tests)
├── .github/workflows/    # CI pipeline
├── main.py               # FastAPI entry point
├── pyproject.toml        # Project metadata and dependencies
├── uv.lock               # Locked dependency versions
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

### End-to-End Smoke Test

With PostgreSQL, Redis, the API, and a Celery worker running:

```bash
# Exercises demo analysis, registration, submission, polling, history, and cache isolation
uv run python scripts/smoke_test.py

# Point at another instance
uv run python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

The script runs a real analysis (including the transformer unless `AI_LIGHT_MODE=True`), creates a
unique test user and analysis records in the target database, and exits non-zero on the first
unexpected response.

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
- **Security job** — `pip-audit` against the locked dependency set
- **Migration job** — `alembic upgrade head` + `alembic check` (schema drift detection)

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Leodyver S. Semilla
