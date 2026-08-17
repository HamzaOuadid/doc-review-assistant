"""Citation grounding check.

`verify_citation` answers exactly one question: does this claimed quote
actually appear, verbatim, in the source document? This is the mechanism
that stands between "the model said so" and "the reviewer can trust it."

We normalize whitespace only (collapse runs of whitespace to a single
space) before comparing -- never fuzzy/edit-distance matching. A citation
that requires "close enough" matching to pass is exactly the kind of
paraphrase-disguised-as-quote this check exists to catch.
"""
import re

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def verify_citation(span: str | None, document_text: str) -> bool:
    """Return True iff `span` is an exact (whitespace-normalized) substring
    of `document_text`. Empty/None spans are never grounded."""
    if not span or not span.strip():
        return False
    return _normalize(span) in _normalize(document_text)
