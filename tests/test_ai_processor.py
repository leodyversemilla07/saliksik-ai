"""Tests for the manuscript pre-review service.

The service used to depend on ``textstat`` and the NLTK sentence tokenizer.
Both were replaced with local implementations (``pyphen`` + a regex sentence
splitter) after the locked environment proved unable to import them, so the
readability metrics are covered here to prevent a silent regression.
"""

import importlib.util
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]

SIMPLE_TEXT = "The cat sat on the mat. The dog ran through the park."
ACADEMIC_TEXT = (
    "Scientific research requires careful methodology, transparent analysis, and reproducible results. "
    "This manuscript evaluates a useful approach and explains its findings clearly. "
    "The proposed method outperforms the baseline on three benchmark datasets."
)


@pytest.fixture(scope="module")
def ai_processor_module():
    spec = importlib.util.spec_from_file_location(
        "saliksik_real_ai_processor", APP_ROOT / "app/services/ai_processor.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def reviewer(ai_processor_module):
    instance = ai_processor_module.ManuscriptPreReviewer()
    # Never download transformer weights in tests.
    instance.light_mode = True
    return instance


def test_split_sentences_handles_common_boundaries(ai_processor_module):
    text = "First sentence. Second one! Is this a third? Yes."

    sentences = ai_processor_module.split_sentences(text)

    assert sentences == ["First sentence.", "Second one!", "Is this a third?", "Yes."]


def test_split_sentences_ignores_empty_input(ai_processor_module):
    assert ai_processor_module.split_sentences("") == []
    assert ai_processor_module.split_sentences("   \n  ") == []


def test_syllable_estimation_is_sane(ai_processor_module):
    estimate = ai_processor_module.ManuscriptPreReviewer._estimate_syllables

    assert estimate("cat") == 1
    assert estimate("methodology") == 4
    assert estimate("beautiful") == 3
    assert estimate("") == 0
    assert estimate("123") == 0


def test_readability_metrics_are_plausible(reviewer):
    metrics = reviewer.assess_language_quality(SIMPLE_TEXT)

    assert metrics["word_count"] == 12
    assert metrics["sentence_count"] == 2
    # Flesch reading ease can exceed 100 for very simple sentences.
    assert 0 < metrics["readability_score"] < 200
    assert metrics["flesch_kincaid_grade"] < 12


def test_readability_is_lower_for_dense_academic_prose(reviewer):
    simple = reviewer.assess_language_quality(SIMPLE_TEXT)
    academic = reviewer.assess_language_quality(ACADEMIC_TEXT)

    assert academic["readability_score"] < simple["readability_score"]
    assert academic["flesch_kincaid_grade"] > simple["flesch_kincaid_grade"]


def test_language_quality_always_contains_readability_score(reviewer):
    metrics = reviewer.assess_language_quality(ACADEMIC_TEXT)

    assert "readability_score" in metrics
    assert "automated_readability" in metrics
    assert metrics["unique_words"] <= metrics["word_count"]


def test_generate_report_structure(reviewer):
    report = reviewer.generate_report(ACADEMIC_TEXT)

    assert set(report) == {"summary", "keywords", "language_quality"}
    assert isinstance(report["summary"], str)
    assert report["summary"]
    assert isinstance(report["keywords"], list)
    assert report["language_quality"]["word_count"] > 0


def test_summary_handles_short_input(reviewer):
    summary = reviewer.generate_summary("Only one short sentence.")

    assert isinstance(summary, str)
    assert summary.strip()
