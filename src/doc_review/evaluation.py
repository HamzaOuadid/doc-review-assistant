"""Evaluation: confidently-wrong rate (binary vs. three-state), citation
grounding accuracy, and a reviewer-time-saved estimate -- the three things
the spec's Definition of Done requires be measured and published.

"Confidently-wrong rate" is the central proof metric of this whole
project: a classifier that's never allowed to say "I don't know" has to
guess on every genuinely ambiguous case, and some fraction of those
guesses will be confidently wrong. Adding the uncertain state should not
eliminate errors -- it should convert "confidently wrong" errors into
"flagged for review" non-errors, without over-flagging so much that
everything becomes uncertain (see `uncertain_rate` and the flag-precision
check in test_evaluation.py, which is how "genuinely ambiguous, not lazy
over-flagging" gets tested).
"""
from dataclasses import dataclass

from doc_review.models import Classification, Extraction, HandLabel

# --- Reviewer-time-saved assumptions ------------------------------------
# These are stated, documented assumptions (not measured), per the spec's
# Definition of Done. Seconds per field-extraction a reviewer would spend:
ASSUMPTIONS = {
    "manual_review_seconds": 90,       # reading the doc cold and deciding, per field
    "verify_include_seconds": 15,      # glance at a provided, grounded citation
    "verify_exclude_seconds": 20,      # confirm a confident "not present" call
    "review_uncertain_seconds": 95,    # full manual review + reading the system's reason
    "rework_wrong_seconds": 150,       # manual review PLUS catching/undoing a wrong confident call
}


@dataclass
class ConfidentlyWrongResult:
    total: int
    confident_predictions: int
    confidently_wrong: int
    uncertain_count: int

    @property
    def confidently_wrong_rate_of_all(self) -> float:
        return self.confidently_wrong / self.total if self.total else 0.0

    @property
    def confidently_wrong_rate_of_confident(self) -> float:
        return self.confidently_wrong / self.confident_predictions if self.confident_predictions else 0.0

    @property
    def uncertain_rate(self) -> float:
        return self.uncertain_count / self.total if self.total else 0.0


def _label_map(hand_labels: list[HandLabel]) -> dict[tuple[str, str], HandLabel]:
    return {(h.document_id, h.field_name): h for h in hand_labels}


def confidently_wrong_rate(
    predictions: list[tuple[str, str, Classification]],
    hand_labels: list[HandLabel],
) -> ConfidentlyWrongResult:
    """predictions: list of (document_id, field_name, predicted_classification).
    Only pairs that have a hand label are scored."""
    labels = _label_map(hand_labels)
    total = 0
    confident = 0
    wrong = 0
    uncertain = 0
    for doc_id, field_name, predicted in predictions:
        truth = labels.get((doc_id, field_name))
        if truth is None:
            continue
        total += 1
        if predicted == "uncertain":
            uncertain += 1
            continue
        confident += 1
        if predicted != truth.correct_classification:
            wrong += 1
    return ConfidentlyWrongResult(
        total=total, confident_predictions=confident, confidently_wrong=wrong, uncertain_count=uncertain,
    )


def force_binary(extractions: list[Extraction], midpoint: float = 0.5) -> list[tuple[str, str, Classification]]:
    """Simulate the "no uncertain state allowed" baseline: every prediction
    is forced to include or exclude by thresholding the same confidence
    score the three-state classifier computed, with no escape hatch for
    ambiguous cases. This is what M4 calls "a forced binary version."
    """
    out = []
    for e in extractions:
        if e.classification in ("include", "exclude"):
            forced: Classification = e.classification
        else:
            # was "uncertain" -- forced binary must still pick one.
            forced = "include" if e.confidence >= midpoint else "exclude"
        out.append((e.document_id, e.field_name, forced))
    return out


def three_state(extractions: list[Extraction]) -> list[tuple[str, str, Classification]]:
    return [(e.document_id, e.field_name, e.classification) for e in extractions]


def grounding_accuracy(extractions: list[Extraction]) -> dict:
    """Of the extractions classified 'include' (the ones a reviewer is
    told to trust), what fraction actually carry a grounded citation?
    Per user story 1's acceptance criterion, this must be 100% by
    construction (classifier.py never emits 'include' without a grounded
    citation) -- this function exists so tests can assert that invariant
    holds end-to-end, not just in the classifier's unit tests.
    """
    included = [e for e in extractions if e.classification == "include"]
    grounded = [e for e in included if e.grounded]
    return {
        "included_count": len(included),
        "grounded_count": len(grounded),
        "grounding_rate": (len(grounded) / len(included)) if included else 1.0,
    }


def reviewer_time_saved(
    extractions: list[Extraction],
    hand_labels: list[HandLabel],
    assumptions: dict = ASSUMPTIONS,
) -> dict:
    """Stated-assumption estimate of reviewer time saved per document,
    based on this evaluation sample's *measured* accuracy (i.e. it charges
    the full rework cost for confidently-wrong predictions, not just the
    fast-path verification cost)."""
    labels = _label_map(hand_labels)
    n_scored = 0
    baseline_seconds = 0.0
    assisted_seconds = 0.0
    for e in extractions:
        truth = labels.get((e.document_id, e.field_name))
        if truth is None:
            continue
        n_scored += 1
        baseline_seconds += assumptions["manual_review_seconds"]
        if e.classification == "uncertain":
            assisted_seconds += assumptions["review_uncertain_seconds"]
        elif e.classification == truth.correct_classification:
            key = "verify_include_seconds" if e.classification == "include" else "verify_exclude_seconds"
            assisted_seconds += assumptions[key]
        else:
            assisted_seconds += assumptions["rework_wrong_seconds"]

    n_docs = len({e.document_id for e in extractions}) or 1
    saved_seconds = baseline_seconds - assisted_seconds
    return {
        "n_field_extractions_scored": n_scored,
        "n_documents": n_docs,
        "baseline_seconds": baseline_seconds,
        "assisted_seconds": assisted_seconds,
        "saved_seconds": saved_seconds,
        "saved_seconds_per_document": saved_seconds / n_docs,
        "percent_time_saved": (saved_seconds / baseline_seconds * 100) if baseline_seconds else 0.0,
        "assumptions": assumptions,
    }
