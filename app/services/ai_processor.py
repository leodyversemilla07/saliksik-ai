import logging
import re
from typing import Optional

import spacy
from pyphen import Pyphen

from app.core.config import settings
from app.core.nlp_models import NLPModelManager

try:
    from transformers import AutoTokenizer, pipeline

    _TRANSFORMERS_AVAILABLE = True
except Exception:
    _TRANSFORMERS_AVAILABLE = False
try:
    import yake

    _YAKE_AVAILABLE = True
except ImportError:
    _YAKE_AVAILABLE = False
logger = logging.getLogger(__name__)


MODEL_NAME = "sshleifer/distilbart-cnn-12-6"  # 306M params, ~600MB (was bart-large-cnn 400M ~1.5GB)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+(?=[A-Z0-9À-ÖØ-Þ\"'“(])")
# CJK and full-width punctuation terminate sentences without a space.
_CJK_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；])\s*")
_HYPHENATOR = Pyphen(lang="en")

# Languages whose readability formulas are calibrated on English. The metrics
# are still computed for other languages, but they are marked as approximate.
_READABILITY_CALIBRATED_LANGUAGES = {"en"}

# CJK characters count as one syllable each.
_CJK_CHARACTER = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")

# Syllable hyphenators per language (populated on demand).
_HYPHENATORS: dict[str, Optional[Pyphen]] = {}


def _get_hyphenator(language: str) -> Optional[Pyphen]:
    """Return a hyphenator for the language, or None when it is not supported."""
    if language in _HYPHENATORS:
        return _HYPHENATORS[language]

    hyphenator: Optional[Pyphen] = None
    try:
        import pyphen

        if language in pyphen.LANGUAGES:
            hyphenator = pyphen.Pyphen(lang=language)
    except Exception as exc:  # pragma: no cover - pyphen is a hard dependency
        logger.debug("No hyphenation dictionary for '%s': %s", language, exc)

    _HYPHENATORS[language] = hyphenator
    return hyphenator


def split_sentences(text: str) -> list[str]:
    """Split text into sentences without requiring downloaded NLTK data."""
    normalized = text.strip()
    if not normalized:
        return []
    # CJK punctuation ends a sentence without a following space, so the
    # boundary is handled separately from the Latin punctuation.
    parts = _CJK_SENTENCE_BOUNDARY.split(normalized)
    sentences: list[str] = []
    for part in parts:
        sentences.extend(part.strip() for part in _SENTENCE_BOUNDARY.split(part) if part.strip())
    return sentences


class ManuscriptPreReviewer:
    def __init__(self, language: str = "en"):
        # Light mode avoids heavy model loading (for tests/CI or constrained environments)
        self.light_mode = settings.AI_LIGHT_MODE

        # Language used for the spaCy pipeline (keyword/grammar helpers).
        self.language = language

        # Lazy-loaded components
        self._nlp = None
        self._summarizer = None
        self._tokenizer = None

        # YAKE keyword extractor
        if _YAKE_AVAILABLE:
            self._yake_extractor = yake.KeywordExtractor(lan="en", n=3, dedupLim=0.9, top=10, features=None)
        else:
            self._yake_extractor = None

    def set_language(self, language: Optional[str]) -> None:
        """Switch the NLP pipeline to another language."""
        if not language:
            return
        normalized = language.lower()
        if normalized != self.language:
            self.language = normalized
            self._nlp = None  # force a reload for the new language

    @property
    def nlp(self):
        if self._nlp is None:
            # The manager caches one model per language and falls back to a
            # blank pipeline when the language model is not installed.
            self._nlp = NLPModelManager.get_model(self.language)
            if self._nlp is None:
                logger.warning("No spaCy model for language '%s'. Falling back to blank 'en' model.", self.language)
                self._nlp = spacy.blank("en")
        return self._nlp

    @property
    def tokenizer(self):
        if self.light_mode:
            return None
        if self._tokenizer is None:
            if not _TRANSFORMERS_AVAILABLE:
                raise RuntimeError("Transformers not available but required (disable via AI_LIGHT_MODE=1)")
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to load tokenizer: {e}")
                raise
        return self._tokenizer

    @property
    def summarizer(self):
        if self.light_mode:
            return None
        if self._summarizer is None:
            if not _TRANSFORMERS_AVAILABLE:
                raise RuntimeError("Transformers not available but required (disable via AI_LIGHT_MODE=1)")
            try:
                self._summarizer = pipeline("summarization", model=MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to load summarizer: {e}")
                raise
        return self._summarizer

    def preprocess_text(self, text):
        """Cleans and preprocesses the text."""
        return " ".join(text.split())

    def split_text(self, text, max_tokens=1024):
        """Splits text into chunks suitable for model input."""
        sentences = split_sentences(text)
        chunks, current_chunk = [], []
        current_length = 0

        if self.light_mode:
            # In light mode, split by sentence count as an approximation
            max_sentences = 20
            for sentence in sentences:
                current_chunk.append(sentence)
                if len(current_chunk) >= max_sentences:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            return chunks

        # Token-based chunking using BART tokenizer
        for sentence in sentences:
            tokenized_sentence = self.tokenizer.encode(sentence, add_special_tokens=False)
            sentence_length = len(tokenized_sentence)

            if current_length + sentence_length > max_tokens:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def generate_summary_from_chunks(self, text_chunks):
        """Generates a summary for each chunk and combines results."""
        if self.light_mode:
            # Heuristic: return first N sentences as "summary" in light mode
            summaries = []
            for chunk in text_chunks:
                sentences = split_sentences(chunk)
                summaries.append(" ".join(sentences[:3]))
            return " ".join(summaries)

        summaries = []
        for chunk in text_chunks:
            word_count = len(chunk.split())
            if word_count < 5:
                summaries.append(chunk)
                continue

            # The final chunk can be shorter than the requested minimum
            # summary length. Scale both limits to the available input.
            input_tokens = len(self.tokenizer.encode(chunk, add_special_tokens=False))
            min_length = min(30, max(5, input_tokens // 2))
            max_length = min(130, max(min_length, input_tokens))
            summary = self.summarizer(
                chunk,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
            )
            summaries.append(summary[0]["summary_text"])
        return " ".join(summaries)

    def generate_summary(self, text):
        """Generates a summary of the text."""
        chunks = self.split_text(text)
        return self.generate_summary_from_chunks(chunks)

    def extract_keywords(self, text, top_n=10):
        """Extracts keywords using YAKE (or TF-IDF fallback)."""
        if self._yake_extractor:
            keywords = self._yake_extractor.extract_keywords(text)
            # YAKE returns (keyword, score) tuples; lower score = more relevant
            return [kw for kw, score in keywords[:top_n]]
        # Fallback: extract nouns via spaCy
        doc = self.nlp(text[:10000])
        nouns = [token.text.lower() for token in doc if token.pos_ == "NOUN" and len(token.text) > 2]
        from collections import Counter

        return [w for w, _ in Counter(nouns).most_common(top_n)]

    @staticmethod
    def _estimate_syllables(word: str, language: str = "en") -> int:
        """Estimate the syllables of a word for the given language."""
        normalized = re.sub(r"[^\w]", "", word.lower(), flags=re.UNICODE)
        if not normalized or not any(char.isalpha() for char in normalized):
            # Pure numbers or punctuation do not add syllables.
            return 0

        # CJK characters are written without spaces and each one is a syllable.
        cjk_characters = _CJK_CHARACTER.findall(normalized)
        if cjk_characters:
            return len(cjk_characters)

        hyphenator = _get_hyphenator(language)
        if hyphenator is not None:
            try:
                syllables = [part for part in hyphenator.inserted(normalized).split("-") if part.strip("-")]
                if syllables:
                    return max(1, len(syllables))
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Hyphenation failed for '%s': %s", normalized, exc)

        if len(normalized) <= 3:
            return 1
        return max(1, len(_HYPHENATOR.inserted(normalized).split("-")))

    def assess_language_quality(self, text):
        """Analyzes readability and language quality metrics."""
        doc = self.nlp(text)

        words = text.split()
        normalized_words = [re.sub(r"[^\w'-]", "", word).lower() for word in words]
        word_count = len(words)
        unique_words = len({word for word in normalized_words if word})
        sentence_count = len(split_sentences(text))
        named_entities = len(doc.ents)
        language = (self.language or "en").lower()

        quality_metrics: dict[str, int | float | bool | str] = {
            "word_count": word_count,
            "unique_words": unique_words,
            "sentence_count": sentence_count,
            "named_entities": named_entities,
            "readability_language": language,
            "readability_approximate": language not in _READABILITY_CALIBRATED_LANGUAGES,
        }

        if sentence_count > 0 and word_count > 0:
            syllable_count = sum(self._estimate_syllables(word, language) for word in normalized_words)
            syllables_per_word = syllable_count / word_count
            words_per_sentence = word_count / sentence_count
            quality_metrics["readability_score"] = round(
                206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word,
                2,
            )
            quality_metrics["flesch_kincaid_grade"] = round(
                0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59,
                2,
            )
            letter_count = sum(1 for char in text if char.isalpha())
            quality_metrics["automated_readability"] = round(
                4.71 * (letter_count / word_count) + 0.5 * words_per_sentence - 21.43,
                2,
            )

        return quality_metrics

    def extract_text_from_pdf(self, pdf_file):
        """Extract text from a PDF file using pypdf."""
        # Imported lazily: pypdf is expensive to import and only needed when a
        # PDF is actually submitted.
        from pypdf import PdfReader

        try:
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise

    def generate_report(self, manuscript_text):
        """Generates a comprehensive AI-assisted pre-review report."""
        preprocessed_text = self.preprocess_text(manuscript_text)
        summary = self.generate_summary(preprocessed_text)
        keywords = self.extract_keywords(preprocessed_text)
        language_quality = self.assess_language_quality(preprocessed_text)

        return {
            "summary": summary,
            "keywords": keywords,
            "language_quality": language_quality,
        }
