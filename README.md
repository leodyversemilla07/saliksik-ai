# Saliksik AI - Manuscript Pre-Review System

An AI-powered manuscript pre-review system built with Django and modern NLP technologies.

## Features

- **🌐 Interactive Web Interface**: User-friendly homepage with live demo
- **🤖 AI-Powered Summarization**: Automatic manuscript summarization using BART model
- **🔍 Keyword Extraction**: TF-IDF based keyword identification
- **📊 Language Quality Analysis**: Grammar checking, readability scoring, and linguistic metrics
- **📄 PDF Support**: Direct PDF manuscript upload and text extraction
- **🔌 REST API**: Secure API endpoints with authentication
- **👤 User Management**: Registration, login, and user profiles
- **🚀 Demo Mode**: Public demo endpoint for testing

## Quick Demo

Visit **http://127.0.0.1:8000/** in your browser for an interactive demo!

No installation required - try the AI analysis directly on the homepage.

## Technology Stack

- **Frontend**: Interactive HTML5 interface with modern CSS and JavaScript
- **Backend**: Django 5.0.6 + Django REST Framework
- **Authentication**: Token-based authentication
- **AI/ML**: spaCy, Transformers (BART), NLTK, scikit-learn
- **Database**: SQLite (development) / PostgreSQL (production)
- **PDF Processing**: pypdf
- **Containerization**: Docker & Docker Compose

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose

### Run with Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai
```

2. Build and run with Docker Compose:
```bash
# Development mode (SQLite)
docker-compose -f docker-compose.dev.yml up --build

# Production mode (with PostgreSQL, Redis, Nginx)
docker-compose up --build
```

3. Access the application:
- **Homepage**: http://localhost:8000/ (Interactive web interface)
- **API Documentation**: http://localhost:8000/api/info/ (JSON API reference)
- **Admin**: http://localhost:8000/admin/
- **Demo**: http://localhost:8000/demo/ (API endpoint)

## Manual Installation

### Prerequisites
- Python 3.8+
- pip
- Virtual environment (recommended)

### Installation Steps

1. Clone and setup environment:
```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. Environment configuration:
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
# At minimum, change SECRET_KEY for production
```

3. Setup AI models and database:
```bash
# Run the automated setup
python setup.py

# Or manually:
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt')"
python manage.py migrate
```

4. Create superuser (optional):
```bash
python manage.py createsuperuser
```

5. Start development server:
```bash
python manage.py runserver
```

## API Documentation

### Authentication Endpoints

#### Register User
```http
POST /auth/register/
Content-Type: application/json

{
  "username": "your_username",
  "email": "your_email@example.com", 
  "password": "your_secure_password"
}
```

#### Login
```http
POST /auth/login/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

Response includes token for authenticated requests:
```json
{
  "message": "Login successful",
  "token": "your_auth_token_here",
  "user_id": 1,
  "username": "your_username"
}
```

#### Get Profile
```http
GET /auth/profile/
Authorization: Token your_auth_token_here
```

### Analysis Endpoints

#### Demo Analysis (Public)
```http
POST /demo/
Content-Type: application/json

{
  "manuscript_text": "Your manuscript text here (max 5000 chars)"
}
```

#### Full Analysis (Authenticated)
```http
POST /pre_review/
Authorization: Token your_auth_token_here
Content-Type: multipart/form-data

# Text input
{
  "manuscript_text": "Your manuscript text here"
}

# OR PDF file upload
{
  "manuscript_file": [PDF file]
}
```

### Example Response
```json
{
  "summary": "AI-generated summary of the manuscript...",
  "keywords": ["artificial intelligence", "machine learning", "neural networks"],
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
    "processing_time": 3.45,
    "user": "username",
    "timestamp": "2025-09-08T10:30:00Z"
  }
}
```

## Development

### Running Tests
```bash
# All tests
python manage.py test

# Specific test module
python manage.py test pre_review.tests.ModelTests
```

### Adding New Features
1. Create feature branch
2. Add tests
3. Implement feature
4. Update documentation
5. Submit pull request

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Required |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS` | Allowed hosts | `127.0.0.1,localhost` |
| `DATABASE_URL` | Database URL | SQLite |
| `MAX_FILE_SIZE_MB` | Max upload size | `10` |
| `API_RATE_LIMIT` | Rate limit | `100/hour` |

## Security Features

- ✅ Token-based authentication
- ✅ Rate limiting
- ✅ CORS protection
- ✅ Input validation
- ✅ File size limits
- ✅ Secure defaults for production

## Deployment

### Docker Deployment
```bash
# Production deployment
docker-compose up -d
```

### Manual Deployment
1. Set `DEBUG=False` in environment
2. Configure production database
3. Set up reverse proxy (nginx)
4. Configure SSL certificates
5. Set up monitoring and logging

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-feature`)
5. Create Pull Request

## License

[Add license information]

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review existing issues

## Roadmap

- [x] Basic AI processing
- [x] Authentication system
- [x] Docker containerization
- [ ] Web interface
- [ ] Batch processing
- [ ] Advanced analytics
- [ ] Multi-language support
