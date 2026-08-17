"""Pydantic data model.

Mirrors the spec's data model (documents / extractions / hand_labels) plus
the extra structure needed to make the three-state classifier's reasoning
inspectable: an ExtractionCandidate is what an LLMClient produces (raw
signal), an Extraction is the final, classified, persisted record.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Classification = Literal["include", "exclude", "uncertain"]


class Document(BaseModel):
    id: str
    source_text: str
    metadata: dict = Field(default_factory=dict)


class FieldSpec(BaseModel):
    """One field the extraction schema asks the pipeline to pull."""

    name: str
    description: str
    # A short instruction shown to a real LLM backend; the fixture backend
    # uses `strong_patterns` / `weak_patterns` on this same object instead.
    guidance: str
    strong_patterns: list[str] = Field(default_factory=list)
    weak_patterns: list[str] = Field(default_factory=list)
    negation_patterns: list[str] = Field(default_factory=list)


class ExtractionSchema(BaseModel):
    fields: list[FieldSpec]

    def get(self, name: str) -> FieldSpec:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(f"no such field: {name}")


class ExtractionCandidate(BaseModel):
    """Raw output of an LLMClient for one (document, field) pair.

    This is backend-agnostic: both the real API-backed client and the
    deterministic fixture client produce this same shape, which is what
    lets the calibration/classification logic downstream be identical
    (and identically testable) regardless of which backend produced it.
    """

    field_name: str
    value: Optional[str] = None
    citation_span: Optional[str] = None
    match_strength: float = 0.0  # backend's own confidence signal, 0..1
    candidate_count: int = 0  # how many raw pattern/semantic hits were found (any tier)
    strong_match: bool = False  # whether at least one hit came from a high-precision signal
    degraded_source: bool = False  # backend detected garbled/redacted/incomplete text near match
    is_negation: bool = False  # backend detected the match affirmatively negates the field
    conflicting_values: list[str] = Field(default_factory=list)  # >1 distinct strong values found
    backend: str = "unknown"
    raw_notes: Optional[str] = None


class ClassificationResult(BaseModel):
    classification: Classification
    reason: Optional[str] = None
    confidence: float = 0.0
    grounded: bool = False


class Extraction(BaseModel):
    document_id: str
    field_name: str
    extracted_value: Optional[str] = None
    citation_span: Optional[str] = None
    classification: Classification
    reason: Optional[str] = None
    confidence: float = 0.0
    grounded: bool = False
    backend: str = "unknown"


class HandLabel(BaseModel):
    document_id: str
    field_name: str
    correct_classification: Classification
    correct_value: Optional[str] = None
    citation_span: Optional[str] = None
    reason: Optional[str] = None
