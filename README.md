# Saliksik AI

**AI-powered manuscript pre-review system for Research Journal Management**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Saliksik AI streamlines the initial manuscript review process by automatically analyzing submitted manuscripts, providing editors and reviewers with instant insights on content quality, readability, and key themes before formal peer review begins.

---

## Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [API Documentation](docs/API_REFERENCE.md)
- [Architecture](#-architecture)
- [Development](docs/CONTRIBUTING.md#development-setup)
- [Deployment](docs/DEPLOYMENT.md)
- [Contributing](docs/CONTRIBUTING.md)
- [License](#-license)

---

## Features

### Core Capabilities
- **AI-Powered Summarization** - Automatic manuscript summarization using BART transformer model
- **Keyword Extraction** - TF-IDF based keyword identification for categorization
- **Language Quality Analysis** - Grammar checking, readability scoring (Flesch Reading Ease), and linguistic metrics
- **PDF Support** - Direct PDF manuscript upload with text extraction
- **Smart Caching** - Redis-based caching with 40-100x speedup on repeated queries
- **User Management** - JWT-based authentication for editorial staff and reviewers

### Technical Features
- **High Performance** - FastAPI framework provides 2-3x faster response times
- **Auto-Generated Docs** - Interactive Swagger UI and ReDoc documentation
- **Async Processing** - Celery task queue for large document processing
- **Docker Ready** - Full containerization with Docker Compose orchestration
- **Database Optimization** - PostgreSQL with connection pooling and indexing
- **Security** - JWT authentication, rate limiting, input validation

---

## Quick Start

### Using Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/saliksik-ai.git
cd saliksik-ai

# Start services with Docker Compose
docker-compose up --build

# Access the application
# - Interactive API Docs: http://localhost:8000/docs
# - Alternative Docs: http://localhost:8000/redoc
# - Health Check: http://localhost:8000/health
```

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download AI models
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt')"

# Configure environment
cp .env.example .env

# Initialize database
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Start server
uvicorn main:app --reload
```

---

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (optional, for caching)
- Docker & Docker Compose (for containerized deployment)

### Step-by-Step Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/saliksik-ai.git
   cd saliksik-ai
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install AI models**
   ```bash
   python -m spacy download en_core_web_sm
   python -c "import nltk; nltk.download('punkt')"
   ```

4. **Configure Database & Environment**
   See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed configuration options.
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Run the application**
   ```bash
   uvicorn main:app --reload
   ```

---

## Usage

### Basic Workflow

1. **Register & Login**
   Get your JWT token via `/api/v1/auth/register` and `/api/v1/auth/login`.

2. **Submit Manuscript**
   Send text or PDF to `/api/v1/analysis/pre-review`.

3. **View Results**
   Get instant analysis on language quality, keywords, and summary.

For detailed request examples, please see the [API Reference](docs/API_REFERENCE.md).

---

## API Documentation

> 📘 **Full API Reference**
>
> For detailed endpoint documentation, request/response schemas, and authentication details, please see [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

### Interactive Documentation

Once running, you can access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Architecture

### Project Structure

```
saliksik-ai/
├── app/
│   ├── api/v1/          # API route handlers
│   ├── core/            # Config, DB, security, caching
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # AI business logic
│   └── utils/           # Utilities
├── docs/                # Project documentation
├── tests/               # Test suite
├── main.py              # FastAPI entry point
└── docker-compose.yml   # Orchestration
```

For a detailed architecture breakdown, see the [Architecture Section](docs/DOCUMENTATION_INDEX.md).

---

## Development

> 🛠️ **Developer Guide**
>
> For development setup, testing standards, and contribution guidelines, please see [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

### Running Tests

```bash
# Run system verification
python tests/test_system.py
```

---

## Deployment

> 🚀 **Deployment Guide**
>
> For production deployment instructions using Docker, Nginx, and Systemd, please see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Contributing

We welcome contributions! Please see [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for details on code of conduct and the pull request process.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made for the research community**
