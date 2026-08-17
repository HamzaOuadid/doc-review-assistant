"""Unit tests for the three-state classifier -- the core, novel logic of
this project. Each test builds an ExtractionCandidate by hand (no LLM
backend, no document corpus needed) so every branch of the calibration
logic in classifier.py is exercised directly and deterministically,
independent of which backend would have produced the candidate in
practice. This is what makes the "genuinely well-calibrated, not
superficial" requirement checkable.
"""
from doc_review.classifier import classify
from doc_review.models import ExtractionCandidate

DOC = (
    "The Agreement shall be governed by the laws of the State of Delaware. "
    "Neither Party may terminate this Agreement for convenience. "
    "This document also mentions Colorado in an unrelated context."
)


def _candidate(**overrides) -> ExtractionCandidate:
    base = dict(
        field_name="governing_law",
        value="Delaware",
        citation_span="governed by the laws of the State of Delaware",
        match_strength=0.9,
        candidate_count=1,
        strong_match=True,
        degraded_source=False,
        is_negation=False,
        conflicting_values=[],
        backend="test",
    )
    base.update(overrides)
    return ExtractionCandidate(**base)


# -- Rule 1: citation grounding gate -------------------------------------

def test_hallucinated_citation_forces_uncertain_even_with_high_confidence():
    c = _candidate(citation_span="a quote that was never in the document", match_strength=0.99)
    result = classify(c, DOC)
    assert result.classification == "uncertain"
    assert result.grounded is False
    assert "hallucin" in result.reason.lower() or "verified" in result.reason.lower()


def test_grounded_citation_with_high_confidence_includes():
    c = _candidate()
    result = classify(c, DOC)
    assert result.classification == "include"
    assert result.grounded is True
    assert result.reason is None


# -- Rule 2: grounded negation -> confident exclude -----------------------

def test_grounded_negation_excludes_with_a_reason():
    c = _candidate(
        field_name="termination_for_convenience",
        value=None,
        citation_span="Neither Party may terminate this Agreement for convenience",
        is_negation=True,
        match_strength=0.9,
    )
    result = classify(c, DOC)
    assert result.classification == "exclude"
    assert result.grounded is True
    assert result.reason is not None  # exclude still gets an explanation, even if not "required"


def test_negation_without_grounding_does_not_exclude():
    """An LLM backend that *claims* negation but can't produce a real
    citation must not get the confident-exclude fast path."""
    c = _candidate(
        field_name="termination_for_convenience",
        citation_span="a fabricated negation clause",
        is_negation=True,
        match_strength=0.9,
    )
    result = classify(c, DOC)
    assert result.classification == "uncertain"


# -- Rule 3: conflicting signals -------------------------------------------

def test_conflicting_values_forces_uncertain():
    c = _candidate(conflicting_values=["Delaware", "Colorado"])
    result = classify(c, DOC)
    assert result.classification == "uncertain"
    assert "conflict" in result.reason.lower()
    assert "Delaware" in result.reason and "Colorado" in result.reason


# -- Rule 4: degraded source text ------------------------------------------

def test_degraded_source_forces_uncertain_regardless_of_confidence():
    c = _candidate(degraded_source=True, match_strength=0.95, raw_notes="digits look garbled")
    result = classify(c, DOC)
    assert result.classification == "uncertain"
    assert result.confidence <= 0.4  # confidence gets capped, not just the label


def test_degraded_source_reason_is_surfaced():
    c = _candidate(degraded_source=True, raw_notes="the source text is redacted in this region")
    result = classify(c, DOC)
    assert "redacted" in result.reason


# -- Rule 5: high-confidence grounded include ------------------------------

def test_below_include_threshold_is_uncertain_not_a_forced_guess():
    c = _candidate(match_strength=0.5)  # below default 0.72 threshold
    result = classify(c, DOC)
    assert result.classification == "uncertain"
    assert "confidence" in result.reason.lower()


def test_at_or_above_include_threshold_includes():
    c = _candidate(match_strength=0.72)
    result = classify(c, DOC)
    assert result.classification == "include"


# -- Rule 6: zero evidence anywhere -> confident exclude -------------------

def test_zero_evidence_is_a_confident_exclude_not_uncertain():
    c = _candidate(
        value=None, citation_span=None, match_strength=0.0,
        candidate_count=0, strong_match=False,
    )
    result = classify(c, DOC)
    assert result.classification == "exclude"
    assert result.reason is not None
    assert result.grounded is False


# -- Rule 7: weak-only evidence -> uncertain, not a forced guess -----------

def test_weak_only_evidence_is_uncertain_not_a_forced_guess():
    """The spec's core edge case: 'extraction with no clear citation
    available -- must default to uncertain, not a forced guess.'"""
    c = _candidate(
        value=None,
        citation_span="This document also mentions Colorado in an unrelated context.",
        match_strength=0.4,
        candidate_count=3,
        strong_match=False,
    )
    result = classify(c, DOC)
    assert result.classification == "uncertain"
    assert "weak" in result.reason.lower() or "ambiguous" in result.reason.lower()


def test_uncertain_always_carries_a_reason():
    """Data model requirement: uncertain classifications require a reason."""
    for c in [
        _candidate(citation_span="fabricated"),
        _candidate(conflicting_values=["A", "B"]),
        _candidate(degraded_source=True, raw_notes="garbled"),
        _candidate(match_strength=0.1),
        _candidate(value=None, match_strength=0.4, strong_match=False, candidate_count=2),
    ]:
        result = classify(c, DOC)
        if result.classification == "uncertain":
            assert result.reason and len(result.reason) > 0
