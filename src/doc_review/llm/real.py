"""Real, API-backed LLMClient implementations.

These are only importable/usable if the relevant SDK is installed and the
relevant API key is configured (see config.py / .env.example). They are
NOT exercised by the default test suite (no key is configured in CI or in
this environment), but they implement the exact same LLMClient protocol
and produce the exact same ExtractionCandidate shape as FixtureLLMClient,
so the calibration logic in classifier.py applies identically to their
output -- see README "What needs a real API key" for the honest split.

Both backends ask the model to self-report the same confidence/ambiguity
signals the fixture backend derives mechanically (match_strength,
candidate_count, strong_match, degraded_source, is_negation,
conflicting_values). We do not trust the model's self-reported
match_strength blindly for the "include" decision -- verify_citation()
still gates everything downstream in classifier.py, so a model that is
confidently wrong about a fabricated quote still gets caught.
"""
from __future__ import annotations

import json
from typing import Any

from doc_review.models import ExtractionCandidate, FieldSpec

_SYSTEM_PROMPT = """You are a precise contract-review extraction assistant.
Given a document and a field to extract, respond with ONLY a JSON object
(no prose, no markdown fences) with exactly these keys:

{
  "value": <string or null - your best short answer for the field>,
  "citation_span": <string or null - an EXACT verbatim quote from the
      document that supports "value". Must be copied character-for-
      character from the document. Never paraphrase. Null if you cannot
      find a supporting quote.>,
  "match_strength": <float 0.0-1.0 - your confidence that "value" and
      "citation_span" are correct and precisely support the field>,
  "candidate_count": <integer - how many distinct places in the document
      you found evidence relevant to this field, including weak/partial
      matches>,
  "strong_match": <boolean - true only if you found a clean, clause-level
      match (not just a passing keyword mention)>,
  "degraded_source": <boolean - true if the relevant part of the document
      looks garbled, redacted, truncated, or otherwise hard to read
      confidently>,
  "is_negation": <boolean - true if the document affirmatively states
      that this field/clause does NOT apply (not merely absent, but
      explicitly negated)>,
  "conflicting_values": <array of strings - populate with 2+ entries only
      if you found multiple grounded matches with materially different
      values (e.g. two different governing-law states)>
}

Be conservative: if you are not sure, set strong_match=false and/or a
lower match_strength rather than guessing. Never fabricate a citation."""


def _user_prompt(document_text: str, field: FieldSpec) -> str:
    return (
        f"Field: {field.name}\n"
        f"Description: {field.description}\n"
        f"Guidance: {field.guidance}\n\n"
        f"Document:\n{document_text}"
    )


def _parse_response(field_name: str, backend: str, raw: str) -> ExtractionCandidate:
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        # A response that isn't even valid JSON is itself a low-confidence
        # signal -- surface it as "no usable evidence" rather than crashing
        # the pipeline; classifier.py will route this to uncertain/exclude.
        return ExtractionCandidate(
            field_name=field_name, value=None, citation_span=None,
            match_strength=0.0, candidate_count=0, strong_match=False,
            backend=backend, raw_notes="backend returned non-JSON output",
        )
    return ExtractionCandidate(
        field_name=field_name,
        value=data.get("value"),
        citation_span=data.get("citation_span"),
        match_strength=float(data.get("match_strength") or 0.0),
        candidate_count=int(data.get("candidate_count") or 0),
        strong_match=bool(data.get("strong_match", False)),
        degraded_source=bool(data.get("degraded_source", False)),
        is_negation=bool(data.get("is_negation", False)),
        conflicting_values=list(data.get("conflicting_values") or []),
        backend=backend,
        raw_notes=data.get("notes"),
    )


class AnthropicLLMClient:
    """Real backend using the Anthropic Messages API. Requires
    ANTHROPIC_API_KEY and the `anthropic` package (pip install -e ".[anthropic]")."""

    def __init__(self, api_key: str, model: str):
        import anthropic  # local import: optional dependency

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self.name = f"anthropic:{model}"

    def extract_field(self, document_text: str, field: FieldSpec) -> ExtractionCandidate:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _user_prompt(document_text, field)}],
        )
        raw = "".join(block.text for block in resp.content if hasattr(block, "text"))
        return _parse_response(field.name, self.name, raw)


class OpenAILLMClient:
    """Real backend using the OpenAI Chat Completions API. Requires
    OPENAI_API_KEY and the `openai` package (pip install -e ".[openai]")."""

    def __init__(self, api_key: str, model: str):
        import openai  # local import: optional dependency

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self.name = f"openai:{model}"

    def extract_field(self, document_text: str, field: FieldSpec) -> ExtractionCandidate:
        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(document_text, field)},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        return _parse_response(field.name, self.name, raw)
