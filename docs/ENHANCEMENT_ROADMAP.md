# Enhancement Roadmap

Tracking document for enhancements to Saliksik AI.

> **Last Updated**: 2025-12-22  
> **Version**: 2.1.0 (All enhancements implemented)

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
- [ ] Research plagiarism detection algorithms (MinHash, SimHash, cosine similarity)
- [ ] Implement text fingerprinting using n-grams
- [ ] Create local document database for comparison
- [ ] Integrate with external APIs (optional: Copyscape, Turnitin API)
- [ ] Add similarity percentage to analysis response
- [ ] Create highlighted report showing matching sections
- [ ] Add configuration for similarity threshold

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
- [ ] Implement reference section detection
- [ ] Parse common citation formats (APA, MLA, Chicago, IEEE)
- [ ] Extract citation metadata (authors, year, title, journal)
- [ ] Validate citation format consistency
- [ ] Count self-citations vs external citations
- [ ] Check for in-text citation matches with reference list
- [ ] Identify potentially outdated references (configurable threshold)
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
- [ ] Create reviewer profile model with expertise areas
- [ ] Implement expertise keyword matching
- [ ] Build topic embedding comparison (using sentence transformers)
- [ ] Consider reviewer workload and availability
- [ ] Account for conflict of interest checks
- [ ] Implement matching score algorithm
- [ ] Create reviewer recommendation ranking
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
- [ ] Implement automatic language detection
- [ ] Load appropriate spaCy models per language
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
v2.0.x (Current)
├── Core manuscript pre-review
├── Summarization, keywords, quality metrics
└── PDF support, caching, async processing

v2.1.0 (Q1 2025)
└── Plagiarism Detection

v2.2.0 (Q2 2025)
└── Citation Analysis

v2.3.0 (Q2-Q3 2025)
└── Reviewer Matching

v2.4.0 (Q3-Q4 2025)
└── Multi-Language Support
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
