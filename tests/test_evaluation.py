"""Tests for evaluation.py: confidently-wrong rate (binary vs. three-
state), grounding accuracy, and reviewer-time-saved. Uses small,
hand-built extraction/hand-label lists so the metric arithmetic is
checked directly, independent of the real corpus (see test_corpus_eval.py
for the full real-corpus run)."""
from doc_review.evaluation import (
    confidently_wrong_rate,
    force_binary,
    grounding_accuracy,
    reviewer_time_saved,
)
from doc_review.models import Extraction, HandLabel


def _label(doc, field, correct):
    return HandLabel(document_id=doc, field_name=field, correct_classification=correct)


def test_confidently_wrong_rate_counts_only_confident_mismatches():
    labels = [_label("d1", "f1", "include"), _label("d1", "f2", "exclude"), _label("d1", "f3", "include")]
    predictions = [("d1", "f1", "include"), ("d1", "f2", "include"), ("d1", "f3", "uncertain")]
    result = confidently_wrong_rate(predictions, labels)
    assert result.total == 3
    assert result.confident_predictions == 2  # f1, f2 (not the uncertain f3)
    assert result.confidently_wrong == 1  # f2: predicted include, truth exclude
    assert result.uncertain_count == 1
    assert result.confidently_wrong_rate_of_confident == 0.5


def test_force_binary_never_emits_uncertain():
    extractions = [
        Extraction(document_id="d1", field_name="f1", classification="uncertain", confidence=0.3),
        Extraction(document_id="d1", field_name="f2", classification="uncertain", confidence=0.9),
        Extraction(document_id="d1", field_name="f3", classification="include", confidence=0.9),
    ]
    forced = force_binary(extractions, midpoint=0.5)
    assert all(cls in ("include", "exclude") for _, _, cls in forced)
    # low-confidence uncertain forced to exclude, high-confidence forced to include
    forced_map = {f: cls for _, f, cls in forced}
    assert forced_map["f1"] == "exclude"
    assert forced_map["f2"] == "include"


def test_binary_is_confidently_wrong_more_often_on_genuinely_ambiguous_cases():
    """The core proof metric: forcing a guess on a genuinely ambiguous
    case (hand-labeled 'uncertain') makes forced-binary wrong by
    definition, while the three-state system correctly abstains."""
    labels = [_label("d1", "f1", "uncertain")]
    three_state_preds = [("d1", "f1", "uncertain")]
    binary_preds = [("d1", "f1", "include")]  # forced to guess

    three = confidently_wrong_rate(three_state_preds, labels)
    binary = confidently_wrong_rate(binary_preds, labels)

    assert three.confidently_wrong == 0
    assert binary.confidently_wrong == 1
    assert binary.confidently_wrong_rate_of_all > three.confidently_wrong_rate_of_all


def test_grounding_accuracy_flags_ungrounded_includes():
    extractions = [
        Extraction(document_id="d1", field_name="f1", classification="include", grounded=True),
        Extraction(document_id="d1", field_name="f2", classification="include", grounded=False),
        Extraction(document_id="d1", field_name="f3", classification="uncertain", grounded=False),
    ]
    result = grounding_accuracy(extractions)
    assert result["included_count"] == 2
    assert result["grounded_count"] == 1
    assert result["grounding_rate"] == 0.5


def test_grounding_accuracy_of_empty_includes_is_vacuously_perfect():
    result = grounding_accuracy([])
    assert result["grounding_rate"] == 1.0


def test_reviewer_time_saved_charges_full_rework_cost_for_wrong_confident_calls():
    labels = [_label("d1", "f1", "include")]
    correct = [Extraction(document_id="d1", field_name="f1", classification="include", confidence=0.9)]
    wrong = [Extraction(document_id="d1", field_name="f1", classification="exclude", confidence=0.9)]

    saved_correct = reviewer_time_saved(correct, labels)
    saved_wrong = reviewer_time_saved(wrong, labels)

    assert saved_correct["saved_seconds"] > saved_wrong["saved_seconds"]
    assert saved_wrong["assisted_seconds"] > saved_correct["assisted_seconds"]
