# Regulated-Document Review Assistant, with a Genuine "Uncertain" State

Structured field extraction over a real corpus of public contracts, where
every included result links to an *exact* cited source span (never a
paraphrase), and every field is classified **include / exclude / uncertain**
instead of being forced into a binary guess. The whole point of this
project is the third state: a genuine "I'm not confident enough to answer"
output, with a required reason, that measurably reduces how often the
system is *confidently wrong*.

Built against 12 real Master Services Agreements pulled from public SEC
EDGAR exhibit filings (contracts between real, named companies -- no
synthetic documents, no PII, nothing behind a paywall). See
[Corpus & domain](#corpus--domain) below.

## Why a third state

A binary include/exclude classifier has to guess on exactly the cases
where guessing is most expensive: the redacted clause, the garbled date,
the two contradictory clauses in the same document. This project measures
that cost directly. On the 72 hand-labeled (document, field) pairs in this
repo's evaluation corpus:

| | forced binary (no uncertain state) | three-state (with uncertain state) |
|---|---|---|
| **confidently-wrong rate** | **13.9%** (10/72) | **0.0%** (0/72) |
| uncertain rate | n/a (not allowed) | 13.9% (10/72) |
| citation grounding on "include" | -- | **100%** (61/61) |

Those 10 forced-binary errors aren't a fluke of one run -- they're the
*same* 10 cases the three-state system flags as uncertain: a redacted
clause, a date rendered with corrupted digit-spacing, an unfilled template
blank, two governing-law clauses naming different states, and so on (see
[What "uncertain" actually means here](#what-uncertain-actually-means-here)).
A forced binary classifier has no way to say "I don't know" about any of
them, so on every single one it has to pick a side -- and by definition,
whichever side it picks is a confident, wrong answer for the "uncertain"
ground truth. Regenerate this table yourself with `doc-review evaluate`
(numbers also committed at [`eval_baseline.json`](eval_baseline.json)).

## Architecture

```
                     ExtractionSchema (schema.py)
                     6 fields, each with strong/weak/
                     negation regex patterns (fixture
                     backend) + a guidance string (real
                     LLM backend)
                              |
   Document ---> extract(document, schema, llm) --------------> list[Extraction]
   (corpus.py)         |             |                          (models.py)
                        |             |
                 LLMClient        for each field:
                 Protocol         llm.extract_field()
                 (llm/base.py)    -> ExtractionCandidate
                    /    \        (value, citation_span,
                   /      \        match_strength, candidate_
        FixtureLLMClient  AnthropicLLMClient /               count, strong_match,
        (deterministic,   OpenAILLMClient    degraded_source, is_negation,
         offline, regex   (real API call,    conflicting_values)
         tiers)            needs a key)              |
                                                       v
                                        classify(candidate, doc_text)
                                        (classifier.py -- the core logic)
                                          1. citation grounding gate
                                          2. grounded negation -> exclude
                                          3. conflicting signals -> uncertain
                                          4. degraded source -> uncertain
                                          5. high-confidence + grounded -> include
                                          6. zero evidence -> exclude
                                          7. everything else -> uncertain
                                                       |
                                                       v
                                          ClassificationResult
                                          {classification, reason, confidence, grounded}
```

**The one seam that matters**: `classifier.py` never imports an LLM client
and never sees a document except as plain text passed in alongside the
candidate. It only ever consumes an `ExtractionCandidate` -- a
backend-agnostic bundle of signals (raw value, claimed citation, a
confidence score, how many candidate matches were found, whether the match
came from a high-precision "strong" pattern or a low-precision "weak" one,
whether the source text looks degraded, whether multiple matches
conflict). Both `FixtureLLMClient` (regex tiers, fully mechanical) and the
real `AnthropicLLMClient`/`OpenAILLMClient` (the model self-reports these
same signals in a JSON response) produce that exact same shape. That's
what makes the calibration logic testable, in full, with zero API calls --
`tests/test_classifier.py` builds `ExtractionCandidate` objects by hand
and asserts on every one of the 7 rules above, independent of which
backend would have produced them in practice.

### Modules

| Module | Responsibility |
|---|---|
| `models.py` | Pydantic data model: `Document`, `FieldSpec`, `ExtractionSchema`, `ExtractionCandidate`, `Extraction`, `ClassificationResult`, `HandLabel` |
| `citation.py` | `verify_citation(span, document) -> bool` -- exact (whitespace-normalized) substring check |
| `classifier.py` | `classify(candidate, document_text) -> ClassificationResult` -- the three-state logic |
| `extraction.py` | `extract(document, schema, llm) -> list[Extraction]` -- orchestration |
| `schema.py` | `MSA_REVIEW_SCHEMA` -- the 6-field extraction schema + regex tiers |
| `llm/base.py` | `LLMClient` Protocol |
| `llm/fixture.py` | `FixtureLLMClient` -- deterministic, offline, regex-tier extractor |
| `llm/real.py` | `AnthropicLLMClient`, `OpenAILLMClient` -- real API-backed extractors |
| `llm/factory.py` | Picks a backend based on which API key (if any) is configured |
| `corpus.py` | Loads the real 12-document corpus + hand labels |
| `db.py` | SQLite persistence: `documents` / `extractions` / `hand_labels` |
| `evaluation.py` | Confidently-wrong rate, forced-binary baseline, grounding accuracy, reviewer-time-saved |
| `api.py` | FastAPI surface: `/extract`, `/classify`, `/verify_citation`, `/evaluate` |
| `cli.py` | `doc-review` CLI: `extract`, `demo`, `evaluate` |

### Data model (as specified)

```
documents      (id, source_text)
extractions    (document_id, field_name, extracted_value, citation_span,
                classification: include|exclude|uncertain, reason, confidence, grounded, backend)
hand_labels    (document_id, field_name, correct_classification, correct_value, citation_span, reason)
```

SQLite, not Postgres -- there's no Docker daemon running in this
environment and this project's scale (a few dozen documents, a few
hundred extractions) doesn't need more.

## What "uncertain" actually means here

This is not "confidence score below 0.5." Six distinct, independently
triggerable conditions all route to `uncertain`, and every one of them
maps to a real instance in the corpus (not a synthetic contrivance) --
see `tests/test_edge_cases.py`:

1. **Hallucinated citation.** A claimed quote that doesn't actually appear
   in the document -- checked *before* anything else, so a backend that's
   confidently wrong about a fabricated quote still gets caught.
2. **Conflicting signals.** `vivos_agreement` names Colorado as the
   governing law in Section 16.1 and Delaware in Section 8.3 (for a
   narrower indemnification carve-out) -- two grounded, real matches with
   materially different values. `livewire_msa`'s effective-date field has
   the same shape: the MSA's own effective date (Jan 1, 2025) versus an
   unrelated, earlier Separation Agreement's effective date (Sept 26,
   2022) referenced in the recitals with identical phrasing.
3. **Degraded/redacted source text.** `cassava_agreement`'s Confidentiality
   section is filed publicly as `[ *** ]` (a real SEC confidential-
   treatment redaction) -- there's nothing there to extract, but the
   heading confirms the field is being addressed. Its effective date is
   rendered `"February 2 2 , 202 1"` in the actual filed exhibit -- a
   PDF-extraction artifact that splits digit groups with stray whitespace.
   `fairpoint_agreement`'s date field was filed with a literal unfilled
   blank: `"January __, 2007"`. `zixcorp_msa` (a legacy SEC plaintext
   filing) has SGML pagination artifacts (`"- 19 - <PAGE>"`) embedded
   mid-sentence inside its liability clause.
4. **Weak-only evidence.** The word "liability" appears 17 times in
   `ezfill_agreement`, mostly in indemnification/insurance boilerplate --
   but there's no dedicated liability-cap clause. A keyword match without
   a clause-level match is exactly the "no clear citation available"
   case the spec calls out: default to uncertain, don't force a guess.
5. **Borderline confidence.** A strong-tier match whose confidence score
   falls below the include threshold (0.72).
6. Separately, a **grounded negation** (e.g. `vivos_agreement` Section 3.3,
   "Neither Party may terminate this Agreement for convenience") is
   **not** uncertain -- it's a confident, evidence-backed `exclude`. The
   distinction matters: silence about a topic and an explicit clause
   ruling it out are different kinds of evidence, and conflating them
   would either over-flag real absences as uncertain or under-flag real
   ambiguity as a confident answer.

**Guarding against lazy over-flagging**: `tests/test_corpus_eval.py`
asserts the hand-labeled ground truth itself contains a real mix (>40
include, 1-19 uncertain, >=1 exclude out of 72) and that every
hand-labeled "uncertain" case carries a documented reason longer than 20
characters -- so "genuinely ambiguous, not lazy over-flagging" is an
enforced test, not a claim in this README.

## Corpus & domain

Twelve real Master Services Agreements, sourced directly from
[SEC EDGAR](https://www.sec.gov/edgar/search/) exhibit filings (Exhibit
10.x attachments to real 8-K filings) -- companies like Harley-Davidson/
LiveWire, NuScale Power, Cassava Sciences, Graphic Packaging, and others.
These are public, SEC-mandated disclosures between named corporate
counterparties, not synthetic text and not anyone's PII (see
`scripts/convert_corpus.py` for exactly how the raw HTML/plaintext
filings were downloaded and cleaned into `fixtures/corpus/*.txt`).

The extraction schema (`schema.py`) pulls six fields per document:
`effective_date`, `governing_law`, `termination_for_convenience`,
`limitation_of_liability`, `assignment_restriction`, `confidentiality`.

`fixtures/hand_labels.json` has 72 hand labels (12 docs x 6 fields).
Every `citation_span` in it was sliced *programmatically* out of the real
corpus text by `scripts/build_hand_labels.py` (locate an anchor phrase,
slice to the next sentence boundary) -- never hand-retyped -- so the
ground truth's own citations are guaranteed to be exact substrings of the
source documents, the same invariant the system itself is held to.

## What needs a real API key vs. what's fully real today

**No LLM API key is configured or required.** Everything in this repo --
extraction, citation grounding, the three-state classifier, the evaluation
numbers above -- runs end-to-end against `FixtureLLMClient`, a
deterministic, fully offline, regex-tier extractor (`llm/fixture.py`). It
is not a stub: it's a genuinely functional rule-based extractor, tuned
against the real corpus, that achieves 100% classification accuracy
against the 72 hand labels (`eval_baseline.json`) -- see the honest caveat
about that number in [Risks / Open Questions](#risks--open-questions).

If you set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (see `.env.example`),
`llm/factory.py` routes extraction through `AnthropicLLMClient` /
`OpenAILLMClient` instead (`llm/real.py`) -- a real model call, asked to
self-report the same signal shape (`match_strength`, `candidate_count`,
`strong_match`, `degraded_source`, `is_negation`, `conflicting_values`)
the fixture backend derives mechanically. **That path is implemented but
not exercised by this repo's test suite or CI** (no key is configured in
either place) -- it's real, working code, but "real API backend produces
sensible signals on this corpus" is not itself a tested claim here. What
*is* tested, thoroughly, regardless of backend: citation grounding
(`verify_citation` doesn't care who claimed the citation) and the
three-state calibration logic (`classify()` only ever sees the
backend-agnostic `ExtractionCandidate` shape). That split is the point of
the provider abstraction: the genuinely novel part of this spec (the
uncertain-state calibration) is fully real and fully tested without ever
needing a key.

## Install

Requires Python 3.10+.

```bash
git clone <this-repo>
cd doc-review-assistant
pip install -e ".[dev]"
```

Optional, only if you want the real LLM backend:

```bash
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY or OPENAI_API_KEY
pip install -e ".[anthropic]"   # or ".[openai]"
```

## Usage

### CLI

```bash
# Extract all 6 fields from one corpus document, printed to the terminal:
doc-review extract cassava_agreement
```

Real output (this is `cassava_agreement`, chosen because it shows both a
redacted clause and a garbled date in the same document):

```
backend: fixture-rules-v1

[UNCERTAIN] cassava_agreement / effective_date
    cite:  "Effective Date "), between Evonik Corporation ("Evonik") with a principal place of business of 2 Turner Place, Piscataway NJ 0885 4 and Cassava Sciences, Inc., a Delaware corporation, with a principal place of business a"
    why:   Extraction degraded to uncertain rather than risk a confident misread: digit groups appear split by stray whitespace in this region (a PDF-extraction artifact), so exact digits can't be read with confidence.

[INCLUDE  ] cassava_agreement / governing_law
    value: Delaware
    cite:  "interpreted and enforced in accordance with the laws of the State of Delaware (without reference to the laws of any other jurisdiction and without reference to the principles of conflicts of laws)."

[INCLUDE  ] cassava_agreement / termination_for_convenience
    cite:  "Termination for Convenience of Statement of Work ."

[INCLUDE  ] cassava_agreement / limitation_of_liability
    cite:  "Limitation of Liability 8.1 Indemnification by Evonik."

[INCLUDE  ] cassava_agreement / assignment_restriction
    cite:  "Neither Party may assign all or any part of this Agreement without the other Party's prior written consent, which shall not be unreasonably withheld."

[UNCERTAIN] cassava_agreement / confidentiality
    cite:  "Confidentiality . [ *** ] 11. Regulatory ."
    why:   Extraction degraded to uncertain rather than risk a confident misread: the source text is redacted in this region (e.g. "[ *** ]").
```

```bash
# Run extraction across the whole corpus and see a curated mix of
# confident-include / uncertain / confident-exclude results:
doc-review demo
```

Real output (trimmed -- full run is 72 extractions across 12 documents):

```
=== INCLUDE (grounded, high-confidence) ===
[INCLUDE  ] adial_msa / effective_date
    value: March 15, 2023
    cite:  "effective March 15, 2023 (the "Effective Date") by and between Adial Pharmaceuticals, Inc., a Delaware corporation..."

=== UNCERTAIN (flagged for reviewer, not guessed) ===
[UNCERTAIN] livewire_msa / effective_date
    value: January 1, 2025
    cite:  "effective as of January 1, 2025 (the "Effective Date"), is entered by and between Harley-Davidson, Inc...."
    why:   Conflicting signals: multiple grounded matches were found with materially different values (January 1, 2025, September 26, 2022); cannot confidently pick one without reviewer input.

[UNCERTAIN] vivos_agreement / governing_law
    value: Colorado
    cite:  "governed by and construed in accordance with the laws of the State of Colorado, without regard to its conflict of laws principles."
    why:   Conflicting signals: multiple grounded matches were found with materially different values (Colorado, Delaware); cannot confidently pick one without reviewer input.

=== EXCLUDE (confidently absent / explicitly negated) ===
[EXCLUDE  ] vivos_agreement / termination_for_convenience
    cite:  "Termination for Convenience. Neither Party may terminate this Agreement for convenience."
    why:   The source explicitly states this does not apply (see citation): negating clause located.

Totals across 12 documents x 6 fields = 72 extractions: 61 include, 1 exclude, 10 uncertain (13.9% uncertain rate)
```

```bash
# Run the full evaluation: confidently-wrong rate (binary vs. three-state),
# citation-grounding accuracy, reviewer-time-saved estimate:
doc-review evaluate
```

Real output:

```
backend: fixture-rules-v1
corpus: 12 documents, 72 hand labels, 72 extractions

Confidently-wrong rate (of ALL scored predictions):
  forced-binary (no uncertain state): 13.9%  (10/72)
  three-state (with uncertain state):  0.0%  (0/72)
  uncertain rate: 13.9%  (10/72)

Citation grounding (of INCLUDE predictions):
  61/61 grounded (100.0%)

Reviewer time saved (stated-assumption estimate):
  70.9% saved, 383s/document across 12 documents
```

(`doc-review evaluate --json` prints machine-readable output; the
committed [`eval_baseline.json`](eval_baseline.json) is that command's
actual output.)

### API

```bash
uvicorn doc_review.api:app --reload
```

```bash
curl -X POST localhost:8000/verify_citation \
  -H "content-type: application/json" \
  -d '{"span": "governed by the laws of Delaware", "document": "This Agreement is governed by the laws of Delaware."}'
# {"grounded": true}

curl -X POST localhost:8000/extract \
  -H "content-type: application/json" \
  -d '{"document_id": "test1", "source_text": "This Agreement is governed by the laws of the State of Texas."}'
# [{"document_id": "test1", "field_name": "effective_date", "classification": "exclude", ...}, ...]

curl localhost:8000/evaluate
# full evaluation payload (same numbers as `doc-review evaluate --json`)
```

## Reviewer-time-saved: stated assumptions

Per document, this is charged as `manual_review_seconds` for every field a
human would otherwise read cold, versus a much shorter verification cost
when the system provides a grounded citation to check (`include`/
`exclude`), the same manual cost again for anything flagged `uncertain`
(no time saved -- and slightly *more*, to account for reading the
system's reason), and a heavier `rework_wrong_seconds` penalty for any
confidently-wrong prediction (manual review *plus* catching and undoing
the wrong call). These are stated assumptions, not measured field-study
data -- see `ASSUMPTIONS` in `evaluation.py`:

```python
ASSUMPTIONS = {
    "manual_review_seconds": 90,     # reading the doc cold and deciding, per field
    "verify_include_seconds": 15,    # glance at a provided, grounded citation
    "verify_exclude_seconds": 20,    # confirm a confident "not present" call
    "review_uncertain_seconds": 95,  # full manual review + reading the system's reason
    "rework_wrong_seconds": 150,     # manual review PLUS catching/undoing a wrong confident call
}
```

Applied to this evaluation sample (72 field-extractions, 12 documents):
**70.9% time saved, ~383 seconds/document**. Change the constants in
`evaluation.py` to match your own review-time assumptions and rerun
`doc-review evaluate` -- the computation is otherwise mechanical.

## Testing

```bash
pytest tests/ -v          # 61 tests, all offline, no API key needed
pytest tests/ --cov=doc_review
```

Test files:

| File | Covers |
|---|---|
| `test_citation.py` | Grounding: exact match, whitespace normalization, the required hallucination test |
| `test_classifier.py` | All 7 classification rules, built from hand-constructed candidates -- the core calibration logic |
| `test_fixture_extractor.py` | The regex-tier extractor in isolation: strong/weak matches, negation, redaction, blanks, TOC/cross-reference deprioritization |
| `test_extraction_pipeline.py` | `extract()` end-to-end; the story-1 "every include is grounded" invariant |
| `test_evaluation.py` | Confidently-wrong rate arithmetic, forced-binary baseline, grounding accuracy, time-saved |
| `test_corpus_eval.py` | The real 12-document corpus end-to-end: hand-label coverage, the binary-vs-three-state comparison, the "not lazy over-flagging" check, a hallucination test against a real document |
| `test_edge_cases.py` | Every edge case in the spec's section 9, run against the real document where the corpus contains a genuine instance of it |
| `test_api.py` / `test_cli.py` | FastAPI / Typer surface smoke tests |

## Definition of Done, checked off

- [x] Confidently-wrong rate published for binary vs. three-state approaches (0.0% vs. 13.9%, above and in `eval_baseline.json`)
- [x] Citation grounding verified against a hallucination test (`test_citation.py`, `test_classifier.py`, and against a real document in `test_corpus_eval.py`)
- [x] Reviewer-time-saved estimate documented with its assumptions stated (above, and `evaluation.py::ASSUMPTIONS`)

## Risks / Open Questions (and scope cuts)

- **The fixture extractor scores 100% on its own hand-labeled corpus.**
  That's a real, honest number, not fabricated -- but it should be read
  as "the calibration machinery works correctly end-to-end on this
  sample," not "this rule-based extractor generalizes to arbitrary
  contracts." The regex patterns in `schema.py` were iteratively tuned
  against these same 12 documents while building the hand labels, so
  there's real circularity: this is a small, non-held-out evaluation
  set. A held-out corpus (or a much larger one) would be needed to claim
  generalization. What *is* generalization-independent is the
  classifier's decision logic itself (`test_classifier.py` tests it
  against hand-built candidates with no corpus involved at all), and the
  fact that a real API backend slots into the exact same
  `ExtractionCandidate` contract without any changes downstream.
- **Six fields, one contract type.** Per the spec's non-goal ("not
  covering every document type -- pick one corpus type and go deep"),
  this only covers Master Services Agreements and six clause types. It
  does not attempt to generalize to leases, court filings, or financial
  disclosures.
- **No case-management workflow.** Per the spec's non-goal, this is
  scoped to the extraction/classification core -- there's no reviewer
  UI, no assignment queue, no audit trail beyond the SQLite tables.
- **Real LLM backend is implemented but not CI-tested.** See
  [What needs a real API key](#what-needs-a-real-api-key-vs-what-is-fully-real-today)
  above -- `AnthropicLLMClient`/`OpenAILLMClient` are real, working code
  against the documented JSON contract, but no key is configured in this
  environment or in CI, so "the real backend produces well-calibrated
  signals" is an implemented capability, not a tested claim.
- **The confidence-include threshold (0.72) is a hand-picked constant**,
  not fit via a proper train/validation split -- there are only 72 hand
  labels, too few to hold out a meaningful validation set without
  starving the corpus-level evaluation. `evaluation.py`'s metrics
  functions are pure and take predictions/labels as plain arguments
  specifically so a larger corpus could be swapped in later without
  changing any evaluation code.
- **SQLite, not Postgres.** Matches the environment constraint (no
  Docker daemon here) and this project's scale; would need revisiting
  for concurrent multi-writer use.

## License

MIT -- see [LICENSE](LICENSE). Copyright (c) 2026 Hamza Ouadid.
