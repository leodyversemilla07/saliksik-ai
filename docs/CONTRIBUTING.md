# Contributing to Saliksik AI

Thank you for your interest in contributing to Saliksik AI! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

### Our Pledge

We pledge to make participation in this project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Accepting constructive criticism gracefully
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment, trolling, or discriminatory comments
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (optional)
- Git
- Code editor (VS Code, PyCharm, etc.)

### Find an Issue

1. Browse [open issues](https://github.com/yourusername/saliksik-ai/issues)
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to let others know you're working on it

### Fork the Repository

1. Fork the repository on GitHub
2. Clone your fork locally:
 ```bash
 git clone https://github.com/YOUR_USERNAME/saliksik-ai.git
 cd saliksik-ai
 ```

---

## Development Setup

### 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# Install in editable mode with dev dependencies
pip install -r requirements.txt
# pip install -r requirements-dev.txt # If exists
```

### 3. Install AI Models

```bash
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt')"
```

### 4. Setup Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

This will automatically run formatters and linters before each commit.

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your local database credentials
```

### 6. Initialize Database

```bash
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 7. Run Development Server

```bash
uvicorn main:app --reload
```

---

## Making Changes

### 1. Create a Branch

Create a descriptive branch name:

```bash
git checkout -b feature/add-plagiarism-detection
# or
git checkout -b fix/cache-timeout-issue
# or
git checkout -b docs/update-api-reference
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/modifications

### 2. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add comments for complex logic
- Update documentation if needed

### 3. Add Tests

- Add tests for new features
- Update existing tests if needed
- Ensure all tests pass:
 ```bash
 python tests/test_system.py
 # or
 pytest # If using pytest
 ```

### 4. Update Documentation

If your changes affect:
- **API endpoints** → Update `API_REFERENCE.md`
- **Installation** → Update `README.md`
- **Deployment** → Update `DEPLOYMENT.md`

---

## Coding Standards

### Python Style Guide

Follow [PEP 8](https://pep8.org/) with these specifications:

**Code Formatting:**
```bash
# Use Black for formatting
black app/ main.py

# Use isort for import sorting
isort app/ main.py
```

**Type Hints:**
```python
# Always include type hints
def process_manuscript(text: str, max_length: int = 5000) -> Dict[str, Any]:
 """Process manuscript text and return analysis."""
 pass
```

**Docstrings:**
```python
def analyze_text(text: str) -> dict:
 """
 Analyze manuscript text using AI models.
 
 Args:
 text: The manuscript text to analyze
 
 Returns:
 Dictionary containing summary, keywords, and quality metrics
 
 Raises:
 ValueError: If text is too short or empty
 """
 pass
```

### FastAPI Best Practices

**Endpoint Design:**
```python
@router.post("/analysis", response_model=AnalysisResponse)
async def analyze_manuscript(
 request: AnalysisRequest,
 current_user: User = Depends(get_current_user),
 db: Session = Depends(get_db)
):
 """Analyze manuscript with proper dependency injection."""
 pass
```

**Error Handling:**
```python
from fastapi import HTTPException, status

if not manuscript_text:
 raise HTTPException(
 status_code=status.HTTP_400_BAD_REQUEST,
 detail="Manuscript text is required"
 )
```

### File Organization

```
app/
├── api/v1/ # API routes only
├── core/ # Core utilities, config
├── models/ # Database models
├── schemas/ # Pydantic schemas
├── services/ # Business logic
└── utils/ # Helper functions
```

---

## Testing

### Running Tests

```bash
# Run all tests
python tests/test_system.py

# Run specific test
python -m pytest tests/test_system.py -v

# Run with coverage
python -m pytest --cov=app tests/
```

### Writing Tests

```python
def test_user_registration():
 """Test user registration endpoint."""
 response = client.post(
 "/api/v1/auth/register",
 json={
 "username": "testuser",
 "email": "test@example.com",
 "password": "testpass123"
 }
 )
 assert response.status_code == 201
 assert "access_token" in response.json()
```

---

## Pull Request Process

### 1. Commit Your Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "Add plagiarism detection feature

- Implement text similarity checking
- Add API endpoint for plagiarism check
- Update documentation
- Add tests for new feature"
```

Commit message format:
```
<type>: <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### 2. Push to Your Fork

```bash
git push origin feature/add-plagiarism-detection
```

### 3. Create Pull Request

1. Go to the original repository on GitHub
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Code refactoring

## Testing
- [ ] All tests pass
- [ ] Added new tests
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Reviewed own code
```

### 4. Address Review Comments

- Respond to reviewer feedback
- Make requested changes
- Push updates to the same branch
- Re-request review when ready

### 5. Merge

Once approved:
- Maintainers will merge your PR
- Your branch will be deleted
- Celebrate! 

---

## Reporting Issues

### Bug Reports

Use the bug report template:

```markdown
**Describe the bug**
Clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.12.1]
- FastAPI version: [e.g., 0.115.0]

**Additional context**
Any other relevant information.
```

### Feature Requests

Use the feature request template:

```markdown
**Is your feature request related to a problem?**
Clear description of the problem.

**Describe the solution you'd like**
Clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions you've thought about.

**Additional context**
Any other relevant information, mockups, examples.
```

---

## Development Guidelines

### API Changes

- Maintain backward compatibility
- Version breaking changes (e.g., `/api/v2/`)
- Update API documentation
- Provide migration guide

### Database Changes

- Create migration scripts
- Test on sample data
- Document schema changes
- Provide rollback procedure

### Security

- Never commit secrets or credentials
- Use environment variables
- Follow OWASP guidelines
- Report security issues privately

---

## Questions?

- [GitHub Discussions](https://github.com/yourusername/saliksik-ai/discussions)
- Email: dev@example.com
- Documentation: See `/docs`

---

**Thank you for contributing to Saliksik AI!**
