# Saliksik AI - Manuscript Pre-Review System

An AI-powered manuscript pre-review system built with Django and modern NLP technologies.

## Features

- **AI-Powered Summarization**: Automatic manuscript summarization using BART model
- **Keyword Extraction**: TF-IDF based keyword identification
- **Language Quality Analysis**: Grammar checking, readability scoring, and linguistic metrics
- **PDF Support**: Direct PDF manuscript upload and text extraction
- **REST API**: Simple API endpoint for integration

## Technology Stack

- **Backend**: Django 5.0.6 + Django REST Framework
- **AI/ML**: spaCy, Transformers (BART), NLTK, scikit-learn
- **Database**: SQLite (development)
- **PDF Processing**: pypdf

## Setup Instructions

### Prerequisites
- Python 3.8+
- pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/leodyversemilla07/saliksik-ai.git
cd saliksik-ai
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Download spaCy language model:
```bash
python -m spacy download en_core_web_sm
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Start development server:
```bash
python manage.py runserver
```

## API Usage

### Pre-Review Endpoint

**URL**: `POST /pre_review/`

**Input Options**:
- `manuscript_file`: PDF file upload
- `manuscript_text`: Direct text input

**Example Response**:
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
  }
}
```

## Development Status

⚠️ **This project is in early development stage**

### Current Limitations
- No authentication/authorization
- Development configuration only
- Limited error handling
- No persistent data storage
- Basic test coverage

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## License

[Add license information]

## Contact

[Add contact information]
