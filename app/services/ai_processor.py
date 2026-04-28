import os

import spacy
from nltk.tokenize import sent_tokenize

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
try:
    import textstat

    _TEXTSTAT_AVAILABLE = True
except ImportError:
    _TEXTSTAT_AVAILABLE = False
import logging

from pypdf import PdfReader

logger = logging.getLogger(__name__)


MODEL_NAME = "sshleifer/distilbart-cnn-12-6"  # 306M params, ~600MB (was bart-large-cnn 400M ~1.5GB)


class ManuscriptPreReviewer:
    def __init__(self):
        # Light mode avoids heavy model loading (for tests/CI or constrained environments)
        self.light_mode = os.getenv("AI_LIGHT_MODE", "0").lower() in (
            "1",
            "true",
            "yes",
        )

        # Lazy-loaded components
        self._nlp = None
        self._summarizer = None
        self._tokenizer = None

        # YAKE keyword extractor
        if _YAKE_AVAILABLE:
            self._yake_extractor = yake.KeywordExtractor(
                lan="en", n=3, dedupLim=0.9, top=10, features=None
            )
        else:
            self._yake_extractor = None

    @property
    def nlp(self):
        if self._nlp is None:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning(
                    "spaCy model 'en_core_web_sm' not found. Falling back to blank 'en' model."
                )
                self._nlp = spacy.blank("en")
        return self._nlp

    @property
    def tokenizer(self):
        if self.light_mode:
            return None
        if self._tokenizer is None:
            if not _TRANSFORMERS_AVAILABLE:
                raise RuntimeError(
                    "Transformers not available but required (disable via AI_LIGHT_MODE=1)"
                )
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
                raise RuntimeError(
                    "Transformers not available but required (disable via AI_LIGHT_MODE=1)"
                )
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
        sentences = sent_tokenize(text)
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
            tokenized_sentence = self.tokenizer.encode(
                sentence, add_special_tokens=False
            )
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
                sentences = sent_tokenize(chunk)
                summaries.append(" ".join(sentences[:3]))
            return " ".join(summaries)

        summaries = []
        for chunk in text_chunks:
            if len(chunk.split()) < 5:
                summaries.append(chunk)
            else:
                summary = self.summarizer(
                    chunk, max_length=130, min_length=30, do_sample=False
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
        nouns = [
            token.text.lower()
            for token in doc
            if token.pos_ == "NOUN" and len(token.text) > 2
        ]
        from collections import Counter

        return [w for w, _ in Counter(nouns).most_common(top_n)]

    def assess_language_quality(self, text):
        """Analyzes readability and language quality metrics."""
        doc = self.nlp(text)

        word_count = len(text.split())
        unique_words = len(set(text.split()))
        sentence_count = len(sent_tokenize(text))
        named_entities = len(doc.ents)

        quality_metrics = {
            "word_count": word_count,
            "unique_words": unique_words,
            "sentence_count": sentence_count,
            "named_entities": named_entities,
        }

        # Use textstat for accurate readability scores
        if _TEXTSTAT_AVAILABLE and sentence_count > 0 and word_count > 10:
            quality_metrics["readability_score"] = round(
                textstat.flesch_reading_ease(text), 2
            )
            quality_metrics["flesch_kincaid_grade"] = round(
                textstat.flesch_kincaid_grade(text), 2
            )
            quality_metrics["automated_readability"] = round(
                textstat.automated_readability_index(text), 2
            )
        elif sentence_count > 0 and word_count > 0:
            # Fallback: simplified Flesch Reading Ease
            syllable_count = len([token for token in doc if token.is_alpha])
            readability_score = (
                206.835
                - 1.015 * (word_count / sentence_count)
                - 84.6 * (syllable_count / word_count)
            )
            quality_metrics["readability_score"] = round(readability_score, 2)

        return quality_metrics

    def extract_text_from_pdf(self, pdf_file):
        """Extract text from a PDF file using pypdf."""
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
