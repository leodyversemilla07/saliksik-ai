# Saliksik AI

**AI-powered manuscript pre-review system for Research Journal Management**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Saliksik AI streamlines the initial manuscript review process by automatically analyzing submitted manuscripts, providing editors and reviewers with instant insights on content quality, readability, and key themes before formal peer review begins.

---

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Architecture](#-architecture)
- [Development](#-development)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Core Capabilities
- 🤖 **AI-Powered Summarization** - Automatic manuscript summarization using BART transformer model
- 🔍 **Keyword Extraction** - TF-IDF based keyword identification for categorization
- 📊 **Language Quality Analysis** - Grammar checking, readability scoring (Flesch Reading Ease), and linguistic metrics
- 📄 **PDF Support** - Direct PDF manuscript upload with text extraction
- 💾 **Smart Caching** - Redis-based caching with 40-100x speedup on repeated queries
- 👤 **User Management** - JWT-based authentication for editorial staff and reviewers

### Technical Features
- ⚡ **High Performance** - FastAPI framework provides 2-3x faster response times
- 📚 **Auto-Generated Docs** - Interactive Swagger UI and ReDoc documentation
- 🔄 **Async Processing** - Celery task queue for large document processing
- 🐳 **Docker Ready** - Full containerization with Docker Compose orchestration
- 📈 **Database Optimization** - PostgreSQL with connection pooling and indexing
- 🔐 **Security** - JWT authentication, rate limiting, input validation

---

## 🚀 Quick Start

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
# Edit .env with your database credentials

# Run database migrations (create tables)
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Start server
uvicorn main:app --reload

# Visit http://localhost:8000/docs
```

---

## 💻 Installation

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
   # spaCy English model
   python -m spacy download en_core_web_sm
   
   # NLTK punkt tokenizer
   python -c "import nltk; nltk.download('punkt')"
   ```

4. **Configure PostgreSQL database**
   ```bash
   # Create database
   createdb saliksik_ai_dev
   
   # Create user
   psql -c "CREATE USER saliksik WITH PASSWORD 'your_password';"
   psql -c "GRANT ALL PRIVILEGES ON DATABASE saliksik_ai_dev TO saliksik;"
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env`:
   ```bash
   DATABASE_URL=postgresql://saliksik:your_password@localhost:5432/saliksik_ai_dev
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   REDIS_URL=redis://localhost:6379/0  # Optional
   ```

6. **Initialize database**
   ```bash
   python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"
   ```

7. **Run the application**
   ```bash
   uvicorn main:app --reload
   ```

---

## 📖 Usage

### Interactive API Documentation

Visit `http://localhost:8000/docs` for the interactive Swagger UI where you can:
- Explore all available endpoints
- Test API requests directly
- View request/response schemas
- Authenticate and try protected endpoints

### Basic Workflow

1. **Register an account**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "username": "editor1",
       "email": "editor@journal.com",
       "password": "SecurePass123!"
     }'
   ```

2. **Login to get JWT token**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{
       "username": "editor1",
       "password": "SecurePass123!"
     }'
   ```

3. **Analyze a manuscript (text)**
   ```bash
   curl -X POST http://localhost:8000/api/v1/analysis/pre-review \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -F "manuscript_text=Your manuscript text here..."
   ```

4. **Analyze a manuscript (PDF)**
   ```bash
   curl -X POST http://localhost:8000/api/v1/analysis/pre-review \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -F "manuscript_file=@manuscript.pdf"
   ```

5. **Try the public demo (no authentication)**
   ```bash
   curl -X POST http://localhost:8000/api/v1/analysis/demo \
     -H "Content-Type: application/json" \
     -d '{
       "manuscript_text": "This is a sample manuscript text for testing the AI analysis system. The system will analyze this text and provide insights."
     }'
   ```

### Response Example

```json
{
  "summary": "AI-generated summary of the manuscript content...",
  "keywords": [
    "machine learning",
    "neural networks",
    "deep learning",
    "artificial intelligence"
  ],
  "language_quality": {
    "word_count": 1250,
    "unique_words": 890,
    "sentence_count": 45,
    "named_entities": 12,
    "grammar_issues": 3,
    "readability_score": 68.5
  },
  "metadata": {
    "analysis_id": 123,
    "input_length": 1250,
    "processing_time": 2.34,
    "user": "editor1",
    "timestamp": "2025-11-07T08:22:54Z",
    "cached": false
  }
}
```

---

## 🔌 API Documentation

### Authentication Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/auth/register` | POST | Register new user | No |
| `/api/v1/auth/login` | POST | Login and get JWT token | No |
| `/api/v1/auth/profile` | GET | Get user profile | Yes |

### Analysis Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/analysis/demo` | POST | Public demo (5000 char limit) | No |
| `/api/v1/analysis/pre-review` | POST | Full manuscript analysis | Yes |
| `/api/v1/analysis/history` | GET | Get analysis history (paginated) | Yes |
| `/api/v1/analysis/cache/stats` | GET | Get cache statistics | No |
| `/api/v1/analysis/cache/clear` | POST | Clear cache | Yes |

### System Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/health` | GET | Health check | No |
| `/api/v1/info` | GET | API information | No |
| `/docs` | GET | Interactive Swagger UI | No |
| `/redoc` | GET | Alternative ReDoc UI | No |

For detailed request/response schemas, visit `/docs` after starting the server.

---

## 🏗️ Architecture

### Project Structure

```
saliksik-ai/
├── app/
│   ├── api/v1/              # API route handlers
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── analysis.py      # Analysis endpoints
│   │   └── info.py          # Information endpoints
│   ├── core/                # Core functionality
│   │   ├── config.py        # Configuration (Pydantic Settings)
│   │   ├── database.py      # SQLAlchemy setup
│   │   ├── security.py      # JWT & password hashing
│   │   ├── cache.py         # Redis caching layer
│   │   └── deps.py          # FastAPI dependencies
│   ├── models/              # Database models (SQLAlchemy)
│   │   ├── user.py          # User model
│   │   └── analysis.py      # Analysis & error models
│   ├── schemas/             # Pydantic schemas (validation)
│   │   ├── user.py          # User schemas
│   │   └── analysis.py      # Analysis schemas
│   ├── services/            # Business logic
│   │   └── ai_processor.py  # AI/ML processing engine
│   └── utils/               # Utility functions
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Multi-service orchestration
└── .env.example            # Environment variables template
```

### Technology Stack

**Backend Framework:**
- FastAPI 0.115+ (Modern, fast web framework)
- Uvicorn (ASGI server)
- Python 3.12+

**Database:**
- PostgreSQL 15+ (Primary database)
- SQLAlchemy 2.0 (ORM)
- Alembic (Migrations - optional)

**Caching & Queue:**
- Redis 7+ (Caching layer)
- Celery 5.5+ (Background tasks)

**AI/ML Libraries:**
- Transformers (BART model for summarization)
- spaCy (NLP processing)
- NLTK (Tokenization)
- scikit-learn (TF-IDF)
- LanguageTool (Grammar checking)

**Security:**
- python-jose (JWT tokens)
- passlib (Password hashing with bcrypt)

---

## 👨‍💻 Development

### Running Tests

```bash
# Run verification tests
python test_migration.py

# Expected output:
# ✅ All imports successful!
# ✅ Password hashing works
# ✅ JWT works
# ✅ AI Processor works
# ✅ Cache works
```

### Development Server

```bash
# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run with specific workers
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000
```

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `SECRET_KEY` | JWT signing key | - | Yes |
| `DEBUG` | Debug mode | `False` | No |
| `REDIS_URL` | Redis connection (optional) | - | No |
| `MAX_FILE_SIZE_MB` | Max upload size | `10` | No |
| `AI_LIGHT_MODE` | Disable heavy models for testing | `False` | No |

### Code Style

```bash
# Format code
black app/ main.py

# Sort imports
isort app/ main.py

# Lint
flake8 app/ main.py
```

---

## 🚢 Deployment

### Docker Deployment (Production)

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Scale workers
docker-compose up -d --scale web=3
```

### Manual Deployment

1. **Set production environment variables**
   ```bash
   export DEBUG=False
   export SECRET_KEY=<strong-random-key>
   export DATABASE_URL=postgresql://user:pass@host:5432/db
   ```

2. **Run with Gunicorn + Uvicorn workers**
   ```bash
   gunicorn main:app \
     --workers 4 \
     --worker-class uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:8000 \
     --access-logfile - \
     --error-logfile -
   ```

3. **Set up Nginx reverse proxy**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure production database
- [ ] Set up Redis for caching
- [ ] Configure SSL/TLS certificates
- [ ] Set up monitoring (Sentry, etc.)
- [ ] Configure backup strategy
- [ ] Set up log aggregation
- [ ] Enable rate limiting
- [ ] Configure CORS properly

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add type hints to all functions
- Write docstrings for public APIs
- Add tests for new features
- Update documentation

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- FastAPI framework by Sebastián Ramírez
- BART model by Facebook AI Research
- spaCy NLP library
- All contributors and users of this project

---

## 📞 Support

For issues, questions, or contributions:

- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/saliksik-ai/issues)
- 📖 Documentation: Visit `/docs` after starting the server
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/saliksik-ai/discussions)

---

**Made with ❤️ for the research community**
