"""The extraction pipeline: extract(document, schema) -> list[Extraction].

Wires an LLMClient (real or fixture) to the three-state classifier. This
module contains no LLM-specific logic and no classification logic of its
own -- it's pure orchestration, which is what makes both of those pieces
independently testable.
"""
from doc_review.classifier import classify
from doc_review.llm.base import LLMClient
from doc_review.models import Document, Extraction, ExtractionSchema


def extract(document: Document, schema: ExtractionSchema, llm: LLMClient) -> list[Extraction]:
    results: list[Extraction] = []
    for field in schema.fields:
        candidate = llm.extract_field(document.source_text, field)
        result = classify(candidate, document.source_text)
        results.append(
            Extraction(
                document_id=document.id,
                field_name=field.name,
                extracted_value=candidate.value,
                citation_span=candidate.citation_span,
                classification=result.classification,
                reason=result.reason,
                confidence=result.confidence,
                grounded=result.grounded,
                backend=candidate.backend,
            )
        )
    return results
