"""
NLP model manager for multi-language support.
Handles lazy loading of spaCy models for different languages.
"""
import logging
from typing import Dict, Optional, Any

try:
    import spacy
    from spacy.language import Language
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    Language = Any

logger = logging.getLogger(__name__)


class NLPModelManager:
    """
    Centralized manager for NLP models across multiple languages.
    
    Implements lazy loading to only load models when needed,
    reducing memory usage and startup time.
    """
    
    # Model cache
    _models: Dict[str, Language] = {}
    
    # Default models for each language
    DEFAULT_MODELS = {
        'en': 'en_core_web_sm',
        'es': 'es_core_news_sm',
        'fr': 'fr_core_news_sm',
        'de': 'de_core_news_sm',
        'pt': 'pt_core_news_sm',
        'it': 'it_core_news_sm',
        'nl': 'nl_core_news_sm',
        'zh': 'zh_core_web_sm',
        'ja': 'ja_core_news_sm',
        'ko': 'ko_core_news_sm',
        'ru': 'ru_core_news_sm',
    }
    
    @classmethod
    def get_model(cls, lang_code: str) -> Optional[Language]:
        """
        Get a spaCy model for the specified language.
        
        Args:
            lang_code: ISO 639-1 language code (e.g., 'en', 'es')
            
        Returns:
            Loaded spaCy Language model, or None if unavailable
        """
        if not SPACY_AVAILABLE:
            logger.warning("spaCy not available")
            return None
        
        # Check cache first
        if lang_code in cls._models:
            return cls._models[lang_code]
        
        # Try to load the model
        return cls.load_model(lang_code)
    
    @classmethod
    def load_model(cls, lang_code: str) -> Optional[Language]:
        """
        Load a spaCy model for the specified language.
        
        Args:
            lang_code: ISO 639-1 language code
            
        Returns:
            Loaded spaCy Language model, or None if unavailable
        """
        if not SPACY_AVAILABLE:
            return None
        
        model_name = cls.DEFAULT_MODELS.get(lang_code)
        
        if not model_name:
            logger.warning(f"No spaCy model configured for language: {lang_code}")
            return None
        
        try:
            model = spacy.load(model_name)
            cls._models[lang_code] = model
            logger.info(f"Loaded spaCy model: {model_name}")
            return model
            
        except OSError:
            logger.warning(
                f"spaCy model '{model_name}' not installed. "
                f"Install with: python -m spacy download {model_name}"
            )
            
            # Try to use blank model as fallback
            try:
                model = spacy.blank(lang_code)
                cls._models[lang_code] = model
                logger.info(f"Using blank spaCy model for: {lang_code}")
                return model
            except Exception:
                return None
                
        except Exception as e:
            logger.error(f"Failed to load spaCy model for {lang_code}: {e}")
            return None
    
    @classmethod
    def is_model_loaded(cls, lang_code: str) -> bool:
        """Check if a model is already loaded."""
        return lang_code in cls._models
    
    @classmethod
    def get_loaded_languages(cls) -> list:
        """Get list of currently loaded language models."""
        return list(cls._models.keys())
    
    @classmethod
    def unload_model(cls, lang_code: str) -> bool:
        """
        Unload a model to free memory.
        
        Args:
            lang_code: Language code of model to unload
            
        Returns:
            True if model was unloaded, False if not loaded
        """
        if lang_code in cls._models:
            del cls._models[lang_code]
            logger.info(f"Unloaded spaCy model for: {lang_code}")
            return True
        return False
    
    @classmethod
    def clear_all(cls) -> int:
        """
        Clear all loaded models.
        
        Returns:
            Number of models cleared
        """
        count = len(cls._models)
        cls._models.clear()
        logger.info(f"Cleared {count} spaCy models")
        return count
    
    @classmethod
    def get_available_models(cls) -> Dict[str, str]:
        """Get dictionary of available language codes and model names."""
        return cls.DEFAULT_MODELS.copy()
    
    @classmethod
    def preload_languages(cls, lang_codes: list) -> Dict[str, bool]:
        """
        Preload models for multiple languages.
        
        Args:
            lang_codes: List of language codes to preload
            
        Returns:
            Dictionary of language codes to success status
        """
        results = {}
        for code in lang_codes:
            model = cls.get_model(code)
            results[code] = model is not None
        return results
