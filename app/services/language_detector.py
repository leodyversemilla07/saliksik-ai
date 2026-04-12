"""
Language detection service for multi-language manuscript support.
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    from langdetect import detect, detect_langs, DetectorFactory

    # Make detection deterministic
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class LanguageInfo:
    """Information about detected language."""

    code: str  # ISO 639-1 code (e.g., 'en', 'es')
    name: str  # Full name (e.g., 'English', 'Spanish')
    confidence: float  # Detection confidence (0.0-1.0)


class LanguageDetector:
    """
    Service for detecting the language of manuscript text.

    Supports automatic detection of common academic languages
    and provides language-specific configurations.
    """

    SUPPORTED_LANGUAGES: Dict[str, Dict[str, Any]] = {
        "en": {
            "name": "English",
            "spacy_model": "en_core_web_sm",
            "language_tool": "en-US",
        },
        "es": {
            "name": "Spanish",
            "spacy_model": "es_core_news_sm",
            "language_tool": "es",
        },
        "fr": {
            "name": "French",
            "spacy_model": "fr_core_news_sm",
            "language_tool": "fr",
        },
        "de": {
            "name": "German",
            "spacy_model": "de_core_news_sm",
            "language_tool": "de-DE",
        },
        "pt": {
            "name": "Portuguese",
            "spacy_model": "pt_core_news_sm",
            "language_tool": "pt-BR",
        },
        "it": {
            "name": "Italian",
            "spacy_model": "it_core_news_sm",
            "language_tool": "it",
        },
        "nl": {
            "name": "Dutch",
            "spacy_model": "nl_core_news_sm",
            "language_tool": "nl",
        },
        "zh": {
            "name": "Chinese",
            "spacy_model": "zh_core_web_sm",
            "language_tool": None,  # Not supported
        },
        "ja": {
            "name": "Japanese",
            "spacy_model": "ja_core_news_sm",
            "language_tool": None,  # Not supported
        },
        "ko": {
            "name": "Korean",
            "spacy_model": "ko_core_news_sm",
            "language_tool": None,  # Not supported
        },
        "ru": {
            "name": "Russian",
            "spacy_model": "ru_core_news_sm",
            "language_tool": "ru",
        },
        "ar": {
            "name": "Arabic",
            "spacy_model": None,  # Not available in spaCy
            "language_tool": None,
        },
    }

    def __init__(self, default_language: str = "en"):
        """
        Initialize the language detector.

        Args:
            default_language: Default language code if detection fails
        """
        self.default_language = default_language

        if not LANGDETECT_AVAILABLE:
            logger.warning(
                "langdetect not available. Language detection will default to English."
            )

        logger.info(f"LanguageDetector initialized (default: {default_language})")

    def detect_language(self, text: str, min_length: int = 20) -> LanguageInfo:
        """
        Detect the language of the given text.

        Args:
            text: Text to analyze
            min_length: Minimum text length for detection

        Returns:
            LanguageInfo with detected language details
        """
        # Return default if text is too short
        if len(text.strip()) < min_length:
            return LanguageInfo(
                code=self.default_language,
                name=self.SUPPORTED_LANGUAGES.get(self.default_language, {}).get(
                    "name", "English"
                ),
                confidence=1.0,
            )

        if not LANGDETECT_AVAILABLE:
            return LanguageInfo(
                code=self.default_language,
                name=self.SUPPORTED_LANGUAGES.get(self.default_language, {}).get(
                    "name", "English"
                ),
                confidence=1.0,
            )

        try:
            # Get language probabilities
            lang_probs = detect_langs(text[:5000])  # Use first 5000 chars for speed

            if not lang_probs:
                return LanguageInfo(
                    code=self.default_language,
                    name=self.SUPPORTED_LANGUAGES.get(self.default_language, {}).get(
                        "name", "English"
                    ),
                    confidence=0.5,
                )

            # Get the most likely language
            top_lang = lang_probs[0]
            lang_code = top_lang.lang
            confidence = top_lang.prob

            # Map to our supported languages
            if lang_code in self.SUPPORTED_LANGUAGES:
                lang_name = self.SUPPORTED_LANGUAGES[lang_code]["name"]
            else:
                # Fall back to default for unsupported languages
                logger.info(
                    f"Detected unsupported language '{lang_code}', falling back to default"
                )
                lang_code = self.default_language
                lang_name = self.SUPPORTED_LANGUAGES.get(self.default_language, {}).get(
                    "name", "English"
                )
                confidence = 0.5

            return LanguageInfo(
                code=lang_code, name=lang_name, confidence=round(confidence, 4)
            )

        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return LanguageInfo(
                code=self.default_language,
                name=self.SUPPORTED_LANGUAGES.get(self.default_language, {}).get(
                    "name", "English"
                ),
                confidence=0.5,
            )

    def is_supported(self, lang_code: str) -> bool:
        """Check if a language is supported."""
        return lang_code in self.SUPPORTED_LANGUAGES

    def get_spacy_model(self, lang_code: str) -> Optional[str]:
        """Get the spaCy model name for a language."""
        if lang_code in self.SUPPORTED_LANGUAGES:
            return self.SUPPORTED_LANGUAGES[lang_code].get("spacy_model")
        return None

    def get_language_tool_code(self, lang_code: str) -> Optional[str]:
        """Get the LanguageTool code for a language."""
        if lang_code in self.SUPPORTED_LANGUAGES:
            return self.SUPPORTED_LANGUAGES[lang_code].get("language_tool")
        return None

    def get_supported_languages(self) -> Dict[str, str]:
        """Get a dictionary of supported language codes and names."""
        return {code: info["name"] for code, info in self.SUPPORTED_LANGUAGES.items()}

    def get_language_info(self, lang_code: str) -> Optional[Dict[str, Any]]:
        """Get full information about a supported language."""
        return self.SUPPORTED_LANGUAGES.get(lang_code)


# Singleton instance
_language_detector: Optional[LanguageDetector] = None


def get_language_detector() -> LanguageDetector:
    """Get or create the singleton LanguageDetector instance."""
    global _language_detector
    if _language_detector is None:
        from app.core.config import settings

        _language_detector = LanguageDetector(
            default_language=settings.DEFAULT_LANGUAGE
        )
    return _language_detector
