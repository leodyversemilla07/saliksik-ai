# Documentation Index

Complete documentation for Saliksik AI

> **Last Updated**: 2026-10-29
>
> The documents below describe the current state of the project. `IMPLEMENTATION_PLAN.md`
> and `TASK_CHECKLIST.md` are historical records of the original enhancement work
> (2025-12-22); the features they describe were audited, fixed and wired into the
> analysis pipeline in 2026-10 — see `CHANGELOG.md` and `ENHANCEMENT_ROADMAP.md`.

## Documentation Files

### Getting Started

1. **[README.md](../README.md)** - Main project documentation
 - Project overview
 - Features and capabilities
 - Quick start guide
 - Installation instructions
 - Basic usage examples
 - Architecture overview
 - Web interface (`/` landing page, `/dashboard`)

### API Documentation

2. **[API_REFERENCE.md](API_REFERENCE.md)** - Complete API reference
 - All endpoints documented
 - Request/response schemas
 - Authentication guide
 - Error responses
 - Rate limiting details
 - Administration endpoints

### Deployment

3. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment guide
 - System requirements
 - Environment setup
 - Manual deployment
 - Nginx configuration
 - SSL/TLS setup
 - Monitoring and backups

### Contributing

4. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines
 - Code of conduct
 - Development setup
 - Coding standards
 - Testing procedures
 - Pull request process
 - Reporting issues

### Roadmap & Implementation

5. **[ENHANCEMENT_ROADMAP.md](ENHANCEMENT_ROADMAP.md)** - Enhancement tracking
 - ✅ Plagiarism Detection (Complete)
 - ✅ Citation Analysis (Complete)
 - ✅ Reviewer Matching (Complete)
 - ✅ Multi-Language Support (Complete)
 - Implementation progress notes

6. **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Technical implementation details
 - File structure and components
 - API endpoints created
 - Dependencies added
 - Configuration options
 - *Historical record of the original implementation*

7. **[TASK_CHECKLIST.md](TASK_CHECKLIST.md)** - Development task tracking
 - Phase-by-phase task breakdown
 - Completion status for all items
 - Post-implementation tasks
 - *Historical record of the original implementation*

## Configuration

- **[.env.example](../.env.example)** - Environment variables template
 - All configuration options
 - Default values
 - Comments and descriptions

## Interactive Documentation

Once the server is running, visit:

- **Landing page**: http://localhost:8000/
 - Service overview and quick start examples

- **Dashboard**: http://localhost:8000/dashboard
 - Register, sign in, submit manuscripts and inspect the results

- **Swagger UI**: http://localhost:8000/docs
 - Interactive API testing
 - Try endpoints directly
 - View request/response schemas

- **ReDoc**: http://localhost:8000/redoc
 - Alternative documentation view
 - Better for reading/printing
 - Clean, professional layout

## Quick Navigation

### For New Users
1. Start with [README.md](../README.md)
2. Explore `/docs` for interactive testing

### For Developers
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Check [API_REFERENCE.md](API_REFERENCE.md)
3. Review code structure in [README.md](../README.md)

### For DevOps
1. Follow [DEPLOYMENT.md](DEPLOYMENT.md)
2. Configure [.env.example](../.env.example)
3. Set up monitoring and backups

## Finding Information

### By Task

**"How do I..."**
- ...install the application? → README.md > Installation
- ...use the API? → API_REFERENCE.md or /docs
- ...use the web interface? → http://localhost:8000/dashboard
- ...deploy to production? → DEPLOYMENT.md
- ...contribute? → CONTRIBUTING.md
- ...configure settings? → .env.example

**"What is..."**
- ...the project structure? → README.md > Architecture
- ...the API endpoint for X? → API_REFERENCE.md
- ...required for deployment? → DEPLOYMENT.md > Prerequisites

**"Where do I find..."**
- ...API examples? → API_REFERENCE.md or /docs
- ...environment variables? → .env.example
- ...deployment commands? → DEPLOYMENT.md
- ...contribution guidelines? → CONTRIBUTING.md

## Documentation Standards

All documentation follows:
- Clear, concise language
- Step-by-step instructions
- Code examples with syntax highlighting
- Cross-references between docs
- Table of contents for navigation

## Keeping Documentation Updated

When making changes:
1. Update relevant documentation files
2. Test all code examples
3. Update version numbers if needed

## Documentation Feedback

Found an issue or have a suggestion?
- Report: [GitHub Issues](https://github.com/leodyversemilla07/saliksik-ai/issues)
- Discuss: [GitHub Discussions](https://github.com/leodyversemilla07/saliksik-ai/discussions)
- Edit: Submit a PR with improvements

---

**Last Updated**: 2026-10-29  
**Documentation Version**: 2.1.0
