"""Tests for FixtureLLMClient: the deterministic, offline extraction
backend. Uses small synthetic documents so each signal (strong/weak match,
negation, degraded text, conflicting values, redaction) is tested in
isolation, in addition to the full real-corpus run in test_corpus_eval.py.
"""
from doc_review.llm.fixture import FixtureLLMClient
from doc_review.models import FieldSpec

client = FixtureLLMClient()

GOVERNING_LAW_FIELD = FieldSpec(
    name="governing_law",
    description="governing law",
    guidance="find it",
    strong_patterns=[r"governed by the laws of (?:the State of )?([A-Z][a-zA-Z]+)"],
    weak_patterns=[r"Governing Law"],
)


def test_strong_match_produces_grounded_high_confidence_candidate():
    text = "Section 9. Governing Law. This Agreement shall be governed by the laws of Nevada, exclusively."
    candidate = client.extract_field(text, GOVERNING_LAW_FIELD)
    assert candidate.strong_match is True
    assert candidate.value == "Nevada"
    assert candidate.citation_span in text  # exact substring
    assert candidate.match_strength >= 0.7


def test_weak_only_match_is_not_strong():
    text = "For details on Governing Law, see Exhibit C attached hereto."
    candidate = client.extract_field(text, GOVERNING_LAW_FIELD)
    assert candidate.strong_match is False
    assert candidate.value is None
    assert candidate.candidate_count >= 1


def test_no_match_at_all_is_zero_evidence():
    text = "This document discusses shipping terms and delivery schedules only."
    candidate = client.extract_field(text, GOVERNING_LAW_FIELD)
    assert candidate.candidate_count == 0
    assert candidate.strong_match is False
    assert candidate.citation_span is None


def test_conflicting_strong_matches_are_captured():
    text = (
        "This Agreement shall be governed by the laws of Texas. "
        "For a separate matter, the Side Letter shall be governed by the laws of Ohio."
    )
    candidate = client.extract_field(text, GOVERNING_LAW_FIELD)
    assert candidate.strong_match is True
    assert set(candidate.conflicting_values) == {"Texas", "Ohio"}


def test_negation_pattern_is_detected():
    field = FieldSpec(
        name="termination_for_convenience",
        description="",
        guidance="",
        strong_patterns=[r"Termination for Convenience"],
        weak_patterns=[r"for convenience"],
        negation_patterns=[r"[Nn]either Party may terminate this Agreement for convenience"],
    )
    text = "Section 8. No Termination for Convenience. Neither Party may terminate this Agreement for convenience."
    candidate = client.extract_field(text, field)
    assert candidate.is_negation is True
    assert candidate.strong_match is True


def test_redacted_region_flags_degraded_source():
    field = FieldSpec(
        name="confidentiality",
        description="",
        guidance="",
        strong_patterns=[r"\bConfidentiality\s*\.\s"],
        weak_patterns=[r"[Cc]onfidential"],
    )
    text = "10. Confidentiality . [ *** ] 11. Other terms follow here as usual in this contract."
    candidate = client.extract_field(text, field)
    assert candidate.strong_match is True
    assert candidate.degraded_source is True
    assert "redact" in (candidate.raw_notes or "").lower()


def test_unfilled_template_blank_flags_degraded_source():
    field = FieldSpec(
        name="effective_date",
        description="",
        guidance="",
        strong_patterns=[r"dated ____?,\s+\d{4}"],
        weak_patterns=[r"Effective Date"],
    )
    text = "This Agreement is dated ____, 2024 (the Effective Date), by and between the parties."
    candidate = client.extract_field(text, field)
    assert candidate.degraded_source is True


def test_toc_and_cross_reference_mentions_are_deprioritized():
    """A table-of-contents entry or a 'Sections X, Y survive' cross-
    reference list should not be mistaken for the operative clause."""
    field = FieldSpec(
        name="limitation_of_liability",
        description="",
        guidance="",
        strong_patterns=[r"Limitation of Liability"],
        weak_patterns=[r"[Ll]iability"],
    )
    text = (
        "Table of Contents ... Article 8 Limitation of Liability 42 Article 9 Indemnification 45 ... "
        "ARTICLE 8. Limitation of Liability. In no event shall either party's aggregate liability "
        "exceed the fees paid in the preceding twelve months."
    )
    candidate = client.extract_field(text, field)
    assert candidate.strong_match is True
    assert "aggregate liability" in candidate.citation_span or "ARTICLE 8" in candidate.citation_span
    assert "42 Article 9" not in candidate.citation_span
