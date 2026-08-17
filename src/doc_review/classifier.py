"""The three-state classifier: include / exclude / uncertain.

This is the core, novel piece of the project. It is deliberately backend-
agnostic -- it only ever sees an ExtractionCandidate (see models.py) and
the raw document text, never an LLM client. That means the exact same
calibration logic runs whether the candidate came from the deterministic
FixtureLLMClient or a real Anthropic/OpenAI call, and it can be (and is,
see tests/test_classifier.py) unit-tested with hand-built candidates that
never touch a document at all.

Decision order (first matching rule wins) -- each rule maps directly to
one of the spec's edge cases:

  1. Grounding check: a claimed citation that doesn't actually appear in
     the document (hallucinated) -> always UNCERTAIN, regardless of how
     confident the backend claims to be. A hallucinated citation is worse
     than no citation, and confidence built on a fake quote is not
     confidence a reviewer should trust.
  2. Grounded negation (source affirmatively says "this does not apply",
     e.g. "Neither Party may terminate this Agreement for convenience")
     -> EXCLUDE, with the negating clause as citation. This is a
     confident, evidence-backed absence -- fundamentally different from
     silence, so it's not lumped in with "no evidence found."
  3. Conflicting signals (multiple grounded matches with materially
     different values, e.g. two different governing-law states) ->
     UNCERTAIN. Real ambiguity, not something to silently pick a winner on.
  4. Degraded source text near the match (redacted, unfilled template
     blank, legacy pagination artifact, PDF digit-spacing corruption) ->
     UNCERTAIN, regardless of nominal match strength. Confidently misreading
     garbled text is exactly the failure mode this exists to prevent.
  5. High-confidence, grounded, strong-tier match -> INCLUDE.
  6. Zero evidence anywhere (no strong or weak hit at all) -> EXCLUDE.
     An exhaustive search that truly finds nothing is itself a legitimate,
     low-risk conclusion -- distinct from rule 2 in that there's no
     citation, but distinct from "ambiguous" in that there's also no
     competing signal to be uncertain about.
  7. Everything else (weak/keyword-only evidence, or a strong match whose
     confidence falls below the include threshold) -> UNCERTAIN. This is
     the "extraction with no clear citation available" edge case: rather
     than forcing a guess, the system says so and explains why.
"""
from doc_review.citation import verify_citation
from doc_review.config import settings
from doc_review.models import ClassificationResult, ExtractionCandidate


def classify(candidate: ExtractionCandidate, document_text: str) -> ClassificationResult:
    # 1. Citation grounding gate -- applies before anything else.
    grounded = False
    if candidate.citation_span:
        grounded = verify_citation(candidate.citation_span, document_text)
        if not grounded:
            return ClassificationResult(
                classification="uncertain",
                reason=(
                    "The claimed citation does not appear verbatim in the source "
                    "document (possible hallucination); a citation that can't be "
                    "verified can't be trusted, so this cannot be included or "
                    "excluded on its basis."
                ),
                confidence=0.0,
                grounded=False,
            )

    # 2. Grounded negation -> confident, evidence-backed exclude.
    if candidate.is_negation and candidate.strong_match and grounded:
        return ClassificationResult(
            classification="exclude",
            reason=(
                "The source explicitly states this does not apply "
                f"(see citation): {candidate.value or 'negating clause located'}."
            ),
            confidence=candidate.match_strength,
            grounded=True,
        )

    # 3. Conflicting signals -> uncertain.
    if candidate.strong_match and len(set(candidate.conflicting_values)) > 1:
        values = ", ".join(sorted(set(candidate.conflicting_values)))
        return ClassificationResult(
            classification="uncertain",
            reason=(
                "Conflicting signals: multiple grounded matches were found with "
                f"materially different values ({values}); cannot confidently pick "
                "one without reviewer input."
            ),
            confidence=candidate.match_strength,
            grounded=grounded,
        )

    # 4. Degraded source text near the match -> uncertain regardless of
    #    nominal confidence.
    if candidate.degraded_source:
        reason = candidate.raw_notes or "source text near the match appears degraded or incomplete"
        return ClassificationResult(
            classification="uncertain",
            reason=f"Extraction degraded to uncertain rather than risk a confident misread: {reason}.",
            confidence=min(candidate.match_strength, 0.4),
            grounded=grounded,
        )

    # 5. High-confidence grounded strong match -> include.
    if candidate.strong_match and grounded and candidate.match_strength >= settings.confidence_include_threshold:
        return ClassificationResult(
            classification="include",
            reason=None,
            confidence=candidate.match_strength,
            grounded=True,
        )

    # 6. Zero evidence anywhere -> confident, if uncited, exclude.
    if candidate.candidate_count == 0:
        return ClassificationResult(
            classification="exclude",
            reason=(
                "No text resembling this field was found anywhere in the document "
                "after an exhaustive pattern search across the full text."
            ),
            confidence=0.8,
            grounded=False,
        )

    # 7. Everything else: weak-only evidence, or a strong match that didn't
    #    clear the include-confidence bar -> uncertain, never a forced guess.
    if not candidate.strong_match:
        reason = (
            "Only weak/ambiguous keyword evidence was found "
            f"({candidate.candidate_count} candidate mention(s)); no clean, "
            "clause-level match for this field, so this is flagged for review "
            "rather than guessed."
        )
    else:
        reason = (
            f"Match confidence ({candidate.match_strength:.2f}) is below the "
            f"include threshold ({settings.confidence_include_threshold:.2f}); "
            "not confident enough to include without reviewer confirmation."
        )
    return ClassificationResult(
        classification="uncertain",
        reason=reason,
        confidence=candidate.match_strength,
        grounded=grounded,
    )
