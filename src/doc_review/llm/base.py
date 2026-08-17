"""The LLMClient protocol: the one seam between "who found this candidate
extraction" (a real API model, or a deterministic offline extractor) and
"what should we conclude from it" (classifier.py, which never imports or
depends on either backend).

Every backend -- real or fixture -- returns the same ExtractionCandidate
shape. That shape is intentionally richer than "here's the value": it
carries the confidence/ambiguity signals (match_strength, candidate_count,
strong_match, degraded_source, is_negation, conflicting_values) that the
three-state classifier needs to decide include/exclude/uncertain. A real
LLM backend is asked to self-report these signals explicitly (see
llm/real.py's prompt); the fixture backend derives them mechanically from
which regex tier matched. Either way, classifier.py treats them
identically -- that's what makes the calibration logic testable without
ever calling a real API.
"""
from typing import Protocol

from doc_review.models import ExtractionCandidate, FieldSpec


class LLMClient(Protocol):
    """A backend that can locate one field's evidence in one document."""

    name: str

    def extract_field(self, document_text: str, field: FieldSpec) -> ExtractionCandidate:
        """Locate the best evidence for `field` in `document_text`."""
        ...
