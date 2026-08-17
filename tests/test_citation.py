"""Citation grounding: the mechanism behind user story 1's acceptance
criterion ("every included field links to an exact source span, not a
paraphrase"). Includes the spec's required hallucination test."""
from doc_review.citation import verify_citation

DOC = "The Agreement shall be governed by the laws of the State of Delaware, without exception."


def test_exact_substring_is_grounded():
    assert verify_citation("governed by the laws of the State of Delaware", DOC) is True


def test_whitespace_only_differences_still_grounded():
    # Whitespace normalization is allowed (not fuzzy matching): a citation
    # copy-pasted with a stray double space or newline shouldn't fail just
    # because of that.
    span = "governed  by the laws of\nthe State of Delaware"
    assert verify_citation(span, DOC) is True


def test_hallucinated_span_is_rejected():
    """The required hallucination test: a fabricated quote that reads
    plausibly but was never in the document must be caught, not trusted."""
    fabricated = "The Agreement shall be governed by the laws of the State of California."
    assert verify_citation(fabricated, DOC) is False


def test_paraphrase_is_rejected():
    paraphrase = "Delaware law governs this Agreement."
    assert verify_citation(paraphrase, DOC) is False


def test_empty_or_none_span_is_never_grounded():
    assert verify_citation("", DOC) is False
    assert verify_citation(None, DOC) is False
    assert verify_citation("   ", DOC) is False


def test_span_from_a_different_document_is_rejected():
    other_doc_span = "This is from a completely different contract entirely."
    assert verify_citation(other_doc_span, DOC) is False
