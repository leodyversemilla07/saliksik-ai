# FastAPI Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    wget \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt')"

# Pre-download HuggingFace BART model
ENV HF_HOME=/root/.cache/huggingface
RUN python - <<'PY'
from transformers import pipeline, BartTokenizer
print('Pre-fetching BART tokenizer...')
BartTokenizer.from_pretrained('facebook/bart-large-cnn')
print('Pre-fetching BART summarization pipeline...')
pipeline('summarization', model='facebook/bart-large-cnn')
print('Done pre-fetching BART artifacts')
PY

# Copy project
COPY . /app/

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
