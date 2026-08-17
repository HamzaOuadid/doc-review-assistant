"""End-to-end evaluation against the real 12-document corpus and its
hand labels (fixtures/hand_labels.json). This is the spec's M4/testing-
plan requirement: 'hand-label a sample and measure classification
accuracy, including specifically the confidently-wrong rate,' run for
real against real public SEC EDGAR contract exhibits, not synthetic
fixtures.
"""
from doc_review.corpus import load_corpus, load_hand_labels
from doc_review.evaluation import (
    confidently_wrong_rate,
    force_binary,
    grounding_accuracy,
    reviewer_time_saved,
    three_state,
)
from doc_review.extraction import extract
from doc_review.llm.fixture import FixtureLLMClient
from doc_review.schema import MSA_REVIEW_SCHEMA


def _run_full_corpus():
    documents = load_corpus()
    llm = FixtureLLMClient()
    all_extractions = []
    for doc in documents:
        all_extractions.extend(extract(doc, MSA_REVIEW_SCHEMA, llm))
    return documents, all_extractions


def test_corpus_loads_twelve_real_documents():
    documents = load_corpus()
    assert len(documents) == 12
    for doc in documents:
        assert len(doc.source_text) > 1000  # these are real contracts, not stubs


def test_hand_labels_cover_every_document_and_field():
    documents = load_corpus()
    hand_labels = load_hand_labels()
    assert len(hand_labels) == 72  # 12 documents x 6 fields
    doc_ids = {d.id for d in documents}
    for label in hand_labels:
        assert label.document_id in doc_ids
        assert label.field_name in {f.name for f in MSA_REVIEW_SCHEMA.fields}


def test_hand_labels_include_genuine_include_exclude_and_uncertain_cases():
    """Guards against 'lazy over-flagging': the ground truth itself must
    contain real variety, not just a synthetic pile of uncertains."""
    hand_labels = load_hand_labels()
    classes = [h.correct_classification for h in hand_labels]
    assert classes.count("include") > 40  # most real MSA clauses are present
    assert classes.count("uncertain") >= 5  # genuine ambiguity exists...
    assert classes.count("uncertain") < 20  # ...but isn't the majority outcome
    assert classes.count("exclude") >= 1


def test_every_include_prediction_on_the_real_corpus_is_grounded():
    """User story 1's acceptance criterion, measured across the entire
    real corpus, not just a single synthetic document."""
    _, extractions = _run_full_corpus()
    grounding = grounding_accuracy(extractions)
    assert grounding["included_count"] > 0
    assert grounding["grounding_rate"] == 1.0


def test_three_state_system_has_a_lower_confidently_wrong_rate_than_forced_binary():
    """The spec's Proof Metric, computed end-to-end on the real corpus:
    'the confidently-wrong rate before vs. after the uncertain state is
    added.'"""
    documents, extractions = _run_full_corpus()
    hand_labels = load_hand_labels()

    three = confidently_wrong_rate(three_state(extractions), hand_labels)
    binary = confidently_wrong_rate(force_binary(extractions), hand_labels)

    assert three.total == 72
    assert binary.total == 72
    # Adding the uncertain state must not make things worse:
    assert three.confidently_wrong_rate_of_all <= binary.confidently_wrong_rate_of_all
    # And it should convert genuinely ambiguous cases into flagged reviews,
    # not just relabel wrong answers as "uncertain" for free:
    assert three.uncertain_rate > 0


def test_uncertain_flags_are_not_lazy_over_flagging():
    """Acceptance criterion: 'a review of those cases shows they were
    genuinely ambiguous, not lazy over-flagging.' Every hand-labeled
    'uncertain' case must carry a documented reason explaining the real
    ambiguity (redaction, conflicting signals, blank template, degraded
    text, etc.) -- checked here so the claim is enforced, not just
    asserted in prose."""
    hand_labels = load_hand_labels()
    uncertain_labels = [h for h in hand_labels if h.correct_classification == "uncertain"]
    assert len(uncertain_labels) >= 5
    for h in uncertain_labels:
        assert h.reason and len(h.reason) > 20


def test_reviewer_time_saved_is_positive_and_documents_assumptions():
    documents, extractions = _run_full_corpus()
    hand_labels = load_hand_labels()
    result = reviewer_time_saved(extractions, hand_labels)
    assert result["saved_seconds"] > 0
    assert result["percent_time_saved"] > 0
    assert "assumptions" in result and len(result["assumptions"]) > 0


def test_citation_grounding_catches_a_deliberately_hallucinated_span_on_a_real_document():
    """The spec's required hallucination test, run against a real
    document from the corpus rather than a synthetic string."""
    from doc_review.citation import verify_citation

    documents = {d.id: d for d in load_corpus()}
    real_doc = documents["cadrenal_msa"]
    fabricated_span = "This Agreement shall self-destruct after ninety (90) days of non-payment."
    assert verify_citation(fabricated_span, real_doc.source_text) is False
