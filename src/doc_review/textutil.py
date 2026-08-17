"""Small text helpers shared by the fixture extractor and the eval/label
tooling. Kept dependency-free and easy to unit test in isolation.
"""
import re

_DEGRADED_DIGIT_RE = re.compile(r"\d\s+\d(?:\s*\d)*")  # e.g. "202 1" / "2 2"
_BLANK_RE = re.compile(r"_{2,}|\[\s*_+\s*\]")  # unfilled template blanks
_REDACTED_RE = re.compile(r"\[\s*\*+\s*\]|\[REDACTED\]|\[CONFIDENTIAL TREATMENT", re.I)
_PAGE_ARTIFACT_RE = re.compile(r"<PAGE>|<TEXT>|-\s*\d{1,4}\s*-\s*<PAGE>")


def looks_degraded(window: str) -> tuple[bool, str | None]:
    """Heuristically flag a text window as garbled/incomplete/redacted.

    Returns (is_degraded, reason) so callers can surface *why* rather than
    just a boolean -- the reason becomes part of the uncertain-state
    explanation shown to a reviewer.
    """
    if _REDACTED_RE.search(window):
        return True, "the source text is redacted in this region (e.g. \"[ *** ]\")"
    if _BLANK_RE.search(window):
        return True, "the source text contains an unfilled template blank in this region"
    if _PAGE_ARTIFACT_RE.search(window):
        return True, "legacy filing pagination artifacts are embedded in the source text in this region"
    # Require 2+ occurrences: a single isolated hit is usually just a page
    # number bumping into a section number (e.g. "9 8.3 Limitation..."),
    # not genuine digit-spacing corruption of a value. Real PDF-extraction
    # corruption (e.g. a date rendered "February 2 2 , 202 1") splits
    # multiple adjacent digit groups.
    if len(_DEGRADED_DIGIT_RE.findall(window)) >= 2:
        return True, "digit groups appear split by stray whitespace in this region (a PDF-extraction artifact), so exact digits can't be read with confidence"
    return False, None


def slice_to_sentence(text: str, start: int, min_len: int = 60, max_len: int = 320) -> str:
    """Slice `text[start:]` out to (approximately) the next sentence
    boundary, so citation spans read as complete clauses rather than
    being cut off mid-word. Always returns an exact substring of `text`.
    """
    window = text[start: start + max_len]
    cut = window.find(". ", min_len)
    if cut != -1:
        return window[: cut + 1]
    return window
