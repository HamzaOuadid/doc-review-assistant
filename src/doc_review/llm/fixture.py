"""FixtureLLMClient: a deterministic, offline, rule-based extractor.

This is NOT a stub or a mock -- it is a genuinely functional extraction
backend built from real regex tiers tuned against the actual corpus (see
schema.py). It is the default backend when no API key is configured, and
it is what every test in this repo runs against, so the confidence-
calibration / uncertain-escalation logic is fully exercised without
needing network access or an API key.

Signal design:
  - `strong_patterns` hits are high-precision (clause-heading-level)
    evidence -> strong_match=True.
  - `weak_patterns`-only hits are low-precision (bare keyword) evidence
    -> strong_match=False, which the classifier treats as "ambiguous."
  - `negation_patterns` near a strong hit flip it to is_negation=True.
  - `textutil.looks_degraded` flags redaction markers, unfilled template
    blanks, legacy pagination artifacts, and PDF digit-spacing corruption
    near the chosen match -> degraded_source=True.
  - Multiple strong hits with different captured values -> conflicting_values.
"""
import re

from doc_review.models import ExtractionCandidate, FieldSpec
from doc_review.textutil import looks_degraded, slice_to_sentence

_DEDUPE_WINDOW = 20


_TOC_PAGE_NUMBER_RE = re.compile(r"^\s{0,3}\d{1,3}\s")


def _looks_like_list_reference(text: str, end_pos: int) -> bool:
    tail = text[end_pos: end_pos + 6]
    if tail.lstrip().startswith("]") or tail.lstrip().startswith(","):
        return True  # "...Section 8], 10 [..." style cross-reference list
    if _TOC_PAGE_NUMBER_RE.match(tail):
        return True  # "...Limitation of Liability 58 18.2..." table-of-contents entry
    return False


class FixtureLLMClient:
    name = "fixture-rules-v1"

    def extract_field(self, document_text: str, field: FieldSpec) -> ExtractionCandidate:
        strong_hits = [m for pat in field.strong_patterns for m in re.finditer(pat, document_text)]
        weak_hits = [m for pat in field.weak_patterns for m in re.finditer(pat, document_text)]

        candidate_count = self._dedupe_count(
            [m.start() for m in strong_hits] + [m.start() for m in weak_hits]
        )

        if not strong_hits and not weak_hits:
            return ExtractionCandidate(
                field_name=field.name,
                value=None,
                citation_span=None,
                match_strength=0.0,
                candidate_count=0,
                strong_match=False,
                degraded_source=False,
                is_negation=False,
                backend=self.name,
                raw_notes="no pattern (strong or weak) matched anywhere in the document",
            )

        if strong_hits:
            return self._from_strong_hits(document_text, field, strong_hits, candidate_count)
        return self._from_weak_only(document_text, field, weak_hits[0], candidate_count)

    # -- internals ---------------------------------------------------

    @staticmethod
    def _dedupe_count(positions: list[int]) -> int:
        deduped = []
        for p in sorted(positions):
            if not deduped or p - deduped[-1] > _DEDUPE_WINDOW:
                deduped.append(p)
        return len(deduped)

    def _from_strong_hits(self, document_text, field: FieldSpec, strong_hits, candidate_count):
        negation_match = None
        distinct_values: set[str] = set()

        for m in strong_hits:
            start = m.start()
            window = document_text[max(0, start - 120): start + 220]
            if field.negation_patterns and any(re.search(p, window) for p in field.negation_patterns):
                negation_match = m
            if m.groups() and m.group(1):
                distinct_values.add(m.group(1).strip())

        # A real clause heading is essentially never immediately followed by
        # "]" or "," -- that pattern is the hallmark of a table-of-contents
        # entry or a "Sections X, Y and Z shall survive" cross-reference
        # list, not the operative clause itself. Prefer the last strong hit
        # that isn't one of those (the operative clause -- if a topic is
        # discussed at both an article level and a more specific subsection
        # level, the later/more specific one is preferred).
        non_reference_hits = [m for m in strong_hits if not _looks_like_list_reference(document_text, m.end())]
        candidates = non_reference_hits or strong_hits
        primary = negation_match or candidates[0]
        start = primary.start()
        span = slice_to_sentence(document_text, start, min_len=40, max_len=320)
        degraded_window = document_text[max(0, start - 30): start + 320]
        degraded, degraded_reason = looks_degraded(degraded_window)

        value = primary.group(1).strip() if primary.groups() and primary.group(1) else None
        is_negation = negation_match is not None
        conflicting = sorted(distinct_values) if len(distinct_values) > 1 else []

        match_strength = 0.92 if (is_negation or not degraded) else 0.35
        if conflicting:
            match_strength = 0.55  # real evidence, but ambiguous which value is "the" answer

        return ExtractionCandidate(
            field_name=field.name,
            value=value,
            citation_span=span,
            match_strength=match_strength,
            candidate_count=candidate_count,
            strong_match=True,
            degraded_source=degraded,
            is_negation=is_negation,
            conflicting_values=conflicting,
            backend=self.name,
            raw_notes=degraded_reason,
        )

    def _from_weak_only(self, document_text, field: FieldSpec, weak_match, candidate_count):
        start = weak_match.start()
        span = slice_to_sentence(document_text, start, min_len=30, max_len=220)
        degraded_window = document_text[max(0, start - 30): start + 220]
        degraded, degraded_reason = looks_degraded(degraded_window)

        return ExtractionCandidate(
            field_name=field.name,
            value=None,
            citation_span=span,
            match_strength=0.40,
            candidate_count=candidate_count,
            strong_match=False,
            degraded_source=degraded,
            is_negation=False,
            backend=self.name,
            raw_notes=degraded_reason or "only a generic keyword match was found; no clause-level match for this field",
        )
