"""Direct tests for the spec's 'Edge Cases & Failure Modes to Handle'
section, each run against real documents from the corpus wherever the
corpus happens to contain a genuine real-world instance of it (it does,
for both), plus a synthetic case for full isolation.

  - "Extraction with no clear citation available -- must default to
    uncertain, not a forced guess."
  - "Document with poor OCR/formatting -- extraction should degrade to
    uncertain rather than confidently misreading garbled text."
"""
from doc_review.corpus import load_corpus
from doc_review.extraction import extract
from doc_review.llm.fixture import FixtureLLMClient
from doc_review.models import ExtractionCandidate, ExtractionSchema, FieldSpec
from doc_review.classifier import classify
from doc_review.schema import MSA_REVIEW_SCHEMA

DOCUMENTS = {d.id: d for d in load_corpus()}


def test_no_clear_citation_defaults_to_uncertain_not_a_guess():
    """Synthetic, isolated version of the no-citation edge case."""
    candidate = ExtractionCandidate(
        field_name="most_favored_nation",
        value=None,
        citation_span="a vague, unrelated mention of pricing terms",
        match_strength=0.35,
        candidate_count=2,
        strong_match=False,
    )
    result = classify(candidate, "This document has a vague, unrelated mention of pricing terms somewhere.")
    assert result.classification == "uncertain"
    assert result.classification != "include"
    assert result.classification != "exclude"  # exclude requires zero evidence, not weak evidence


def test_real_document_with_a_redacted_clause_degrades_to_uncertain():
    """Real-world instance: cassava_agreement's Section 10 (Confidentiality)
    is redacted in the actual public SEC filing (marked "[ *** ]")."""
    doc = DOCUMENTS["cassava_agreement"]
    results = extract(doc, MSA_REVIEW_SCHEMA, FixtureLLMClient())
    confidentiality = next(r for r in results if r.field_name == "confidentiality")
    assert confidentiality.classification == "uncertain"
    assert confidentiality.classification != "include"  # never confidently misread a redacted clause
    assert "redact" in confidentiality.reason.lower()


def test_real_document_with_garbled_pdf_extracted_date_degrades_to_uncertain():
    """Real-world instance: cassava_agreement's effective date is rendered
    "February 2 2 , 202 1" in the actual filed exhibit (a PDF-to-text
    extraction artifact) -- the digits genuinely can't be read with
    confidence, so this must not be confidently (mis)included."""
    doc = DOCUMENTS["cassava_agreement"]
    results = extract(doc, MSA_REVIEW_SCHEMA, FixtureLLMClient())
    effective_date = next(r for r in results if r.field_name == "effective_date")
    assert effective_date.classification == "uncertain"
    assert effective_date.extracted_value is None  # never confidently asserts a misread date


def test_real_document_with_an_unfilled_template_blank_degrades_to_uncertain():
    """Real-world instance: fairpoint_agreement's exhibit was filed with an
    unfilled date blank ("January __, 2007")."""
    doc = DOCUMENTS["fairpoint_agreement"]
    results = extract(doc, MSA_REVIEW_SCHEMA, FixtureLLMClient())
    effective_date = next(r for r in results if r.field_name == "effective_date")
    assert effective_date.classification == "uncertain"


def test_real_document_with_two_conflicting_governing_law_clauses_is_uncertain():
    """Real-world instance: vivos_agreement names Colorado for the
    Agreement generally (Sec 16.1) and Delaware for officer-indemnification
    matters (Sec 8.3) -- genuinely conflicting signals, not a coin flip."""
    doc = DOCUMENTS["vivos_agreement"]
    results = extract(doc, MSA_REVIEW_SCHEMA, FixtureLLMClient())
    governing_law = next(r for r in results if r.field_name == "governing_law")
    assert governing_law.classification == "uncertain"
    assert "conflict" in governing_law.reason.lower()


def test_real_document_with_an_explicit_negation_is_a_confident_grounded_exclude():
    """Real-world instance: vivos_agreement Section 3.3 explicitly rules
    out termination for convenience -- this should NOT be lumped in with
    'uncertain,' since it's a confident, grounded, evidence-backed
    conclusion, not silence."""
    doc = DOCUMENTS["vivos_agreement"]
    results = extract(doc, MSA_REVIEW_SCHEMA, FixtureLLMClient())
    termination = next(r for r in results if r.field_name == "termination_for_convenience")
    assert termination.classification == "exclude"
    assert termination.grounded is True
    assert termination.citation_span in doc.source_text


def test_legacy_sgml_pagination_artifacts_degrade_to_uncertain():
    """Real-world instance: zixcorp_msa is a legacy SEC plaintext (.txt)
    filing whose liability clause has an SGML pagination artifact
    ("- 19 - <PAGE>") embedded mid-sentence."""
    doc = DOCUMENTS["zixcorp_msa"]
    results = extract(doc, MSA_REVIEW_SCHEMA, FixtureLLMClient())
    liability = next(r for r in results if r.field_name == "limitation_of_liability")
    assert liability.classification == "uncertain"
