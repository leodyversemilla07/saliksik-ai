# Enhancement Roadmap

Tracking document for enhancements to Saliksik AI.

> **Last Updated**: 2026-10-28  
> **Version**: 2.1.0 (enhancements implemented and wired into the API/task pipeline)
>
> The four enhancement areas below are implemented end-to-end: the plagiarism
> detector, citation analyzer, reviewer matcher and language detector are called
> from the Celery task, their results are persisted and returned by the analysis
> endpoints, and each area has regression tests. The unchecked items below are
> genuine follow-ups (external plagiarism APIs, a multilingual summariser,
> LanguageTool integration, an admin UI).

---

## Overview

This document tracks planned enhancements to extend Saliksik AI's capabilities beyond the current manuscript pre-review features. Each enhancement includes implementation details, priority, and progress tracking.

---

## Enhancement Status Legend

| Status | Meaning |
|--------|---------|
| ⬜ Not Started | Enhancement not yet begun |
| 🟡 In Progress | Currently being implemented |
| 🟢 Completed | Fully implemented and tested |
| 🔵 Testing | Implementation complete, under testing |
| ⏸️ On Hold | Temporarily paused |

---

## Planned Enhancements

### 1. Plagiarism Detection

| Property | Details |
|----------|---------|
| **Status** | 🟢 Completed |
| **Priority** | 🔴 High |
| **Estimated Effort** | 2-3 weeks |
| **Target Version** | v2.1.0 |

#### Description
Add similarity checking to detect potential plagiarism in submitted manuscripts by comparing against a database of existing documents and/or external sources.

#### Implementation Approach
- [x] Research plagiarism detection algorithms (MinHash, SimHash, cosine similarity)
- [x] Implement text fingerprinting using n-grams
- [x] Create local document database for comparison
- [ ] Integrate with external APIs (optional: Copyscape, Turnitin API)
- [x] Add similarity percentage to analysis response
- [ ] Create highlighted report showing matching sections
- [x] Add configuration for similarity threshold

#### Technical Components
```
app/
├── services/
│   └── plagiarism_detector.py    # New service
├── models/
│   └── document_fingerprint.py   # Store document hashes
├── api/v1/
│   └── plagiarism.py             # New endpoints
└── schemas/
    └── plagiarism.py             # Response schemas
```

#### API Endpoints
- `POST /api/v1/analysis/plagiarism-check` - Check manuscript for plagiarism
- `GET /api/v1/analysis/{id}/plagiarism-report` - Get detailed plagiarism report

#### Dependencies
- `datasketch` - MinHash LSH for similarity
- `simhash` - Document fingerprinting

#### Progress Notes
| Date | Note |
|------|------|
| 2025-12-22 | Enhancement documented |
| 2025-12-22 | ✅ Implementation completed - `plagiarism_detector.py`, `document_fingerprint.py`, `plagiarism.py` endpoints |

---

### 2. Citation Analysis

| Property | Details |
|----------|---------|
| **Status** | 🟢 Completed |
| **Priority** | 🟡 Medium |
| **Estimated Effort** | 2 weeks |
| **Target Version** | v2.2.0 |

#### Description
Parse and analyze references/citations in manuscripts to validate formatting, check for missing citations, and provide citation statistics.

#### Implementation Approach
- [x] Implement reference section detection
- [x] Parse common citation formats (APA, MLA, Chicago, IEEE)
- [x] Extract citation metadata (authors, year, title, journal)
- [x] Validate citation format consistency
- [x] Count self-citations vs external citations
- [x] Check for in-text citation matches with reference list
- [x] Identify potentially outdated references (configurable threshold)
- [ ] Optional: DOI/CrossRef verification

#### Technical Components
```
app/
├── services/
│   └── citation_analyzer.py      # Citation parsing & analysis
├── schemas/
│   └── citation.py               # Citation response schemas
└── utils/
    └── citation_parsers/
        ├── apa.py
        ├── mla.py
        ├── ieee.py
        └── chicago.py
```

#### API Response Extension
```json
{
  "citation_analysis": {
    "total_citations": 45,
    "valid_citations": 42,
    "format_detected": "APA",
    "format_consistency": 93.3,
    "self_citations": 5,
    "average_citation_age": 4.2,
    "oldest_citation_year": 2015,
    "newest_citation_year": 2024,
    "missing_in_text": ["Smith2020", "Jones2019"],
    "issues": [
      {"line": 234, "issue": "Inconsistent format", "citation": "..."}
    ]
  }
}
```

#### Dependencies
- `refextract` or custom regex patterns
- `crossref-commons` (optional, for DOI verification)

#### Progress Notes
| Date | Note |
|------|------|
| 2025-12-22 | Enhancement documented |
| 2025-12-22 | ✅ Implementation completed - `citation_analyzer.py` service with APA/MLA/IEEE/Chicago support |

---

### 3. Reviewer Matching

| Property | Details |
|----------|---------|
| **Status** | 🟢 Completed |
| **Priority** | 🟡 Medium |
| **Estimated Effort** | 3 weeks |
| **Target Version** | v2.3.0 |

#### Description
Automatically suggest appropriate reviewers based on manuscript keywords, topics, and reviewer expertise profiles.

#### Implementation Approach
- [x] Create reviewer profile model with expertise areas
- [x] Implement expertise keyword matching
- [x] Build topic embedding comparison (using sentence transformers)
- [x] Consider reviewer workload and availability
- [x] Account for conflict of interest checks
- [x] Implement matching score algorithm
- [x] Create reviewer recommendation ranking
- [ ] Add admin interface for reviewer management

#### Technical Components
```
app/
├── models/
│   ├── reviewer.py               # Reviewer profiles
│   └── expertise.py              # Expertise areas
├── services/
│   └── reviewer_matcher.py       # Matching algorithm
├── api/v1/
│   └── reviewers.py              # Reviewer management endpoints
└── schemas/
    └── reviewer.py               # Reviewer schemas
```

#### Database Models
```python
class Reviewer(Base):
    id: int
    user_id: int (FK)
    expertise_keywords: List[str]
    expertise_embedding: Vector
    availability: bool
    current_assignments: int
    max_assignments: int
    institution: str
    orcid_id: str (optional)

class ReviewerMatch(Base):
    id: int
    analysis_id: int (FK)
    reviewer_id: int (FK)
    match_score: float
    matched_keywords: List[str]
    status: str  # suggested, invited, accepted, declined
```

#### API Endpoints
- `POST /api/v1/reviewers` - Create reviewer profile
- `GET /api/v1/reviewers` - List reviewers with filters
- `GET /api/v1/analysis/{id}/suggested-reviewers` - Get reviewer suggestions
- `POST /api/v1/analysis/{id}/assign-reviewer` - Assign reviewer

#### Dependencies
- `sentence-transformers` - For semantic similarity
- `faiss` or `annoy` - For efficient similarity search (if scaling)

#### Progress Notes
| Date | Note |
|------|------|
| 2025-12-22 | Enhancement documented |
| 2025-12-22 | ✅ Implementation completed - `reviewer.py` model, `reviewer_matcher.py` service, `reviewers.py` API |

---

### 4. Multi-Language Support

| Property | Details |
|----------|---------|
| **Status** | 🟢 Completed |
| **Priority** | 🟢 Low |
| **Estimated Effort** | 2-3 weeks |
| **Target Version** | v2.4.0 |

#### Description
Extend language support beyond English to detect manuscript language and provide appropriate analysis using language-specific NLP models.

#### Implementation Approach
- [x] Implement automatic language detection
- [x] Load appropriate spaCy models per language
- [ ] Use multilingual summarization model (mBART or mT5)
- [ ] Adapt readability metrics for different languages
- [ ] Configure LanguageTool for detected language
- [ ] Add language-specific stop words for keyword extraction
- [ ] Support mixed-language documents (detect primary language)

#### Supported Languages (Initial)
| Language | spaCy Model | Priority |
|----------|-------------|----------|
| English | `en_core_web_sm` | ✅ Current |
| Spanish | `es_core_news_sm` | Phase 1 |
| French | `fr_core_news_sm` | Phase 1 |
| German | `de_core_news_sm` | Phase 1 |
| Chinese | `zh_core_web_sm` | Phase 2 |
| Japanese | `ja_core_news_sm` | Phase 2 |

#### Technical Components
```
app/
├── services/
│   ├── language_detector.py      # Language detection
│   └── ai_processor.py           # Updated for multi-lang
├── core/
│   └── nlp_models.py             # Model loader per language
└── config/
    └── languages.py              # Language configurations
```

#### Configuration Addition
```python
# .env
SUPPORTED_LANGUAGES=en,es,fr,de
DEFAULT_LANGUAGE=en
AUTO_DETECT_LANGUAGE=true
```

#### API Response Extension
```json
{
  "language": {
    "detected": "es",
    "confidence": 0.97,
    "name": "Spanish"
  },
  "summary": "Resumen generado del manuscrito...",
  ...
}
```

#### Dependencies
- `langdetect` or `fasttext` - Language detection
- `spacy` models per language
- `transformers` multilingual models

#### Progress Notes
| Date | Note |
|------|------|
| 2025-12-22 | Enhancement documented |
| 2025-12-22 | ✅ Implementation completed - `language_detector.py`, `nlp_models.py` for multi-language support |

---

## Follow-ups (not implemented yet)

The four enhancement areas above are live. These are the genuine remaining
gaps, in the order in which they are worth tackling:

| # | Follow-up | Scope | Notes |
|---|-----------|-------|-------|
| 1 | Multilingual summariser | Medium | The pipeline detects the language and switches the spaCy model, but the summary itself is still produced by the English DistilBART model. A multilingual checkpoint (mBART / mT5) would fix this; it also means a different model download and a larger image. |
| 2 | Language-specific readability metrics | Small | Partially done: syllables are counted per language and the response flags the values as approximate outside English. Language-specific *formulas* (calibrated coefficients) are still missing. |
| 3 | DOI / CrossRef verification | Medium | The citation analyser parses references locally. Verifying DOIs against CrossRef would require an outbound HTTP dependency, caching and a rate-limit budget. |
| 4 | Mixed-language documents | Medium | A manuscript with several languages currently falls back to the dominant language; per-section detection is not implemented. |
| 5 | LanguageTool grammar checks | Medium | `grammar_issues` stays `None` unless a LanguageTool server is reachable; the project deliberately avoids the Java dependency. |
| 6 | Administration UI | Small | Done: the dashboard has an administration view (statistics, user list, role changes). |
| 7 | External plagiarism sources | Large | The detector only compares against the documents of the same tenant. Cross-checking with an external corpus (Crossref, Turnitin-like APIs) needs credentials and a compliance review. |

---

## Implementation Priority Matrix

| Enhancement | Impact | Effort | Priority Score |
|-------------|--------|--------|----------------|
| Plagiarism Detection | High | Medium | 🔴 **1st** |
| Citation Analysis | Medium | Medium | 🟡 **2nd** |
| Reviewer Matching | Medium | High | 🟡 **3rd** |
| Multi-Language | Medium | Medium | 🟢 **4th** |

---

## Version Roadmap

```
v2.0.x
├── Core manuscript pre-review
├── Summarization, keywords, quality metrics
└── PDF support, caching, async processing

v2.1.0
└── Plagiarism Detection, Citation Analysis, Reviewer Matching,
    Multi-Language Support

v2.2.0 (current)
├── Authentication hardening (token types, revocation, password reset)
├── Administration API and bundled web interface
├── Dependency refresh and CI end-to-end job
└── Follow-ups 1-6 of the list above
```

---

## Contributing to Enhancements

If you'd like to contribute to any of these enhancements:

1. Check the current status in this document
2. Review the implementation approach
3. Create a feature branch: `feature/enhancement-name`
4. Follow the technical components structure
5. Add tests for new functionality
6. Update this document with progress notes
7. Submit a pull request

---

## References

- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [API_REFERENCE.md](API_REFERENCE.md) - Current API documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide

---

**Maintained by**: Saliksik AI Development Team  
**Contact**: [GitHub Issues](https://github.com/leodyversemilla07/saliksik-ai/issues)
