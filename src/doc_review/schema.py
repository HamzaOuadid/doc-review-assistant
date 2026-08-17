"""The extraction schema: six clause-level fields pulled from Master
Services Agreements (the corpus type -- see fixtures/corpus/, real public
SEC EDGAR exhibits). Each field carries the guidance text sent to a real
LLM backend, plus the regex tiers the deterministic FixtureLLMClient uses:

- strong_patterns: high-precision, clause-heading-level signals. A hit
  here is real evidence the field is actually being addressed (not just
  a stray keyword).
- weak_patterns: low-precision, single-keyword signals. A hit here alone
  (no strong hit) means "the topic is mentioned somewhere" but not
  "here is the clause" -- exactly the ambiguous case that should be
  flagged uncertain rather than guessed.
- negation_patterns: phrases that, near a strong match, mean the clause
  explicitly says the opposite (e.g. "no termination for convenience").
"""
from doc_review.models import ExtractionSchema, FieldSpec

MSA_REVIEW_SCHEMA = ExtractionSchema(
    fields=[
        FieldSpec(
            name="effective_date",
            description="The date the agreement becomes effective.",
            guidance=(
                "Find the agreement's effective date -- the calendar date the "
                "contract itself states it becomes effective, usually near the "
                "preamble (\"entered into as of ...\", \"effective as of ...\", "
                "\"dated ...\"). Quote the exact sentence containing the date."
            ),
            strong_patterns=[
                r"(?:as of|dated as of|dated|effective as of|effective on|effective|made on|entered into on)\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
            ],
            weak_patterns=[r"[Ee]ffective\s+[Dd]ate"],
        ),
        FieldSpec(
            name="governing_law",
            description="The state/jurisdiction whose law governs the agreement.",
            guidance=(
                "Find the governing-law clause and quote the sentence naming the "
                "jurisdiction whose law governs the agreement."
            ),
            strong_patterns=[
                r"governed by.{0,60}?[Ll]aws of (?:the (?:State|Commonwealth) of )?([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2})",
                r"(?:construed and enforced|interpreted and enforced) in accordance with the [Ll]aws of (?:the (?:State|Commonwealth) of )?([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2})",
            ],
            weak_patterns=[r"[Gg]overning\s+[Ll]aw"],
        ),
        FieldSpec(
            name="termination_for_convenience",
            description="Whether either party may terminate the agreement for convenience (without cause).",
            guidance=(
                "Determine whether the agreement lets a party terminate for "
                "convenience (without cause). Quote the clause if present, or "
                "the clause that explicitly rules it out if the agreement says "
                "termination for convenience is NOT permitted."
            ),
            strong_patterns=[r"[Tt]ermination\s+for\s+[Cc]onvenience"],
            weak_patterns=[r"for\s+convenience\b", r"without\s+cause\b"],
            negation_patterns=[
                r"[Nn]o\s+Termination\s+for\s+Convenience",
                r"[Nn]either\s+Party\s+may\s+terminate\s+this\s+Agreement\s+for\s+convenience",
                r"may\s+not\s+terminate\s+this\s+Agreement\s+for\s+convenience",
            ],
        ),
        FieldSpec(
            name="limitation_of_liability",
            description="Whether the agreement caps or limits either party's liability.",
            guidance=(
                "Find the limitation-of-liability clause (a liability cap, or a "
                "waiver of consequential/indirect damages) and quote it."
            ),
            strong_patterns=[
                r"[Ll]imitation\s+(?:on|of)\s+(?:Consequential\s+)?[Ll]iabilit(?:y|ies)",
                r"[Ll]imitation\s+on\s+(?:Consequential|Direct)\s+Damages",
                r"IN\s+NO\s+EVENT\s+SHALL\b.{0,90}?(?:BE\s+)?LIABLE",
                r"REMEDIES\s+AND\s+LIMIT\s+OF\s+LIABILITY",
                r"WARRANTY\s+AND\s+LIABILITY",
                r"shall\s+not\s+be\s+(?:responsible|liable)\s+(?:to|for).{0,60}?(?:indirect|consequential|special|incidental)",
                r"neither\s+[Pp]arty\s+shall\s+be\s+.{0,50}?liable.{0,50}?(?:indirect|consequential|special|incidental)",
            ],
            weak_patterns=[r"\b[Ll]iabilit(?:y|ies)\b"],
        ),
        FieldSpec(
            name="assignment_restriction",
            description="Whether the agreement restricts assigning/transferring it to a third party.",
            guidance=(
                "Find the clause restricting (or explicitly permitting) "
                "assignment/transfer of the agreement itself to a third party. "
                "Ignore unrelated uses of 'assign' (e.g. assigning IP rights, "
                "assigning personnel, or 'successors and assigns' boilerplate "
                "inside other clauses) unless they are the actual assignment "
                "clause."
            ),
            strong_patterns=[
                r"\bAssignment\s*[:.]\s",
                r"\bASSIGNMENT\b\s*[-:.]",
                r"[Nn]either\s+[Pp]arty\s+may\s+assign",
                r"(?:may|shall)\s+not\s+assign\s+this\s+Agreement",
                r"(?:may|shall)\s+not\s+assign\s+any\s+of\b",
                r"[Nn]o\s+party\s+may\s+assign\s+this\s+Agreement",
            ],
            weak_patterns=[r"\bassign(?:s|ed|ment|ing|able|ee)?\b"],
        ),
        FieldSpec(
            name="confidentiality",
            description="Whether the agreement defines and protects Confidential Information.",
            guidance=(
                "Find the definition of Confidential Information and/or the "
                "confidentiality obligation, and quote it."
            ),
            strong_patterns=[
                r"Confidential\s+Information.{0,10}(?:means|shall\s+mean)",
                r"^\s*CONFIDENTIALITY\b",
                r"\bConfidentiality\s*\.\s",
                r"\bConfidential\s+Information\s*\.\s",
            ],
            weak_patterns=[r"[Cc]onfidential"],
        ),
    ]
)
