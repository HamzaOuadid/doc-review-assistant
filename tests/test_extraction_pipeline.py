"""Integration tests: extract(document, schema, llm) -> list[Extraction],
per the spec's API contract. Ties FixtureLLMClient + classify() together
end-to-end and checks the story-1 acceptance criterion directly: every
'include' result must carry a citation that is grounded in the document.
"""
from doc_review.extraction import extract
from doc_review.llm.fixture import FixtureLLMClient
from doc_review.models import ExtractionSchema, FieldSpec


def test_extract_returns_one_result_per_field(sample_document):
    schema = ExtractionSchema(fields=[
        FieldSpec(
            name="governing_law", description="", guidance="",
            strong_patterns=[r"governed by and construed in accordance with the laws of (?:the State of )?([A-Z][a-zA-Z]+)"],
            weak_patterns=[r"Governing Law"],
        ),
        FieldSpec(
            name="unrelated_field", description="", guidance="",
            strong_patterns=[r"Force Majeure"], weak_patterns=[r"force majeure"],
        ),
    ])
    results = extract(sample_document, schema, FixtureLLMClient())
    assert len(results) == 2
    assert {r.field_name for r in results} == {"governing_law", "unrelated_field"}


def test_every_include_result_is_grounded(sample_document):
    """User story 1's acceptance criterion, exercised end-to-end."""
    schema = ExtractionSchema(fields=[
        FieldSpec(
            name="governing_law", description="", guidance="",
            strong_patterns=[r"governed by and construed in accordance with the laws of (?:the State of )?([A-Z][a-zA-Z]+)"],
            weak_patterns=[r"Governing Law"],
        ),
    ])
    results = extract(sample_document, schema, FixtureLLMClient())
    included = [r for r in results if r.classification == "include"]
    assert included, "expected at least one include to make this test meaningful"
    for r in included:
        assert r.grounded is True
        assert r.citation_span is not None
        assert r.citation_span in sample_document.source_text


def test_field_with_no_evidence_is_excluded_not_included(sample_document):
    schema = ExtractionSchema(fields=[
        FieldSpec(
            name="most_favored_nation", description="", guidance="",
            strong_patterns=[r"[Mm]ost [Ff]avored [Nn]ation"],
            weak_patterns=[r"MFN"],
        ),
    ])
    results = extract(sample_document, schema, FixtureLLMClient())
    assert results[0].classification == "exclude"
    assert results[0].classification != "include"
