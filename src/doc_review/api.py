"""FastAPI surface implementing the spec's API/interface contract:
  - extract(document, schema) -> list[Extraction]
  - classify(extraction) -> {classification, reason?}
  - verify_citation(span, document) -> bool
plus thin REST wrappers for ingesting documents and running evaluation.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from doc_review.citation import verify_citation as _verify_citation
from doc_review.classifier import classify as _classify
from doc_review.config import settings
from doc_review.corpus import load_corpus, load_hand_labels
from doc_review.db import get_extractions, init_db, insert_document, insert_extractions
from doc_review.evaluation import (
    confidently_wrong_rate,
    force_binary,
    grounding_accuracy,
    reviewer_time_saved,
    three_state,
)
from doc_review.extraction import extract as _extract
from doc_review.llm.factory import get_default_llm_client
from doc_review.models import Document, ExtractionCandidate
from doc_review.schema import MSA_REVIEW_SCHEMA

_llm = get_default_llm_client()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db(settings.db_path)
    yield


app = FastAPI(title="Regulated-Document Review Assistant", version="0.1.0", lifespan=_lifespan)


class ExtractRequest(BaseModel):
    document_id: str
    source_text: str


class VerifyCitationRequest(BaseModel):
    span: str
    document: str


class ClassifyRequest(BaseModel):
    candidate: ExtractionCandidate
    document_text: str


@app.post("/documents")
def ingest_document(req: ExtractRequest) -> dict:
    doc = Document(id=req.document_id, source_text=req.source_text)
    insert_document(settings.db_path, doc)
    return {"status": "ok", "document_id": doc.id}


@app.post("/extract")
def extract_endpoint(req: ExtractRequest) -> list[dict]:
    doc = Document(id=req.document_id, source_text=req.source_text)
    insert_document(settings.db_path, doc)
    extractions = _extract(doc, MSA_REVIEW_SCHEMA, _llm)
    insert_extractions(settings.db_path, extractions)
    return [e.model_dump() for e in extractions]


@app.get("/documents/{document_id}/extractions")
def get_document_extractions(document_id: str) -> list[dict]:
    extractions = get_extractions(settings.db_path, document_id)
    if not extractions:
        raise HTTPException(status_code=404, detail="no extractions for this document; call /extract first")
    return [e.model_dump() for e in extractions]


@app.post("/classify")
def classify_endpoint(req: ClassifyRequest) -> dict:
    result = _classify(req.candidate, req.document_text)
    return result.model_dump()


@app.post("/verify_citation")
def verify_citation_endpoint(req: VerifyCitationRequest) -> dict:
    return {"grounded": _verify_citation(req.span, req.document)}


@app.get("/evaluate")
def evaluate_endpoint() -> dict:
    documents = load_corpus()
    hand_labels = load_hand_labels()
    all_extractions = []
    for doc in documents:
        all_extractions.extend(_extract(doc, MSA_REVIEW_SCHEMA, _llm))

    three = confidently_wrong_rate(three_state(all_extractions), hand_labels)
    binary = confidently_wrong_rate(force_binary(all_extractions), hand_labels)
    grounding = grounding_accuracy(all_extractions)
    time_saved = reviewer_time_saved(all_extractions, hand_labels)

    return {
        "n_documents": len(documents),
        "n_extractions": len(all_extractions),
        "three_state": {
            "confidently_wrong_rate_of_all": three.confidently_wrong_rate_of_all,
            "confidently_wrong_rate_of_confident": three.confidently_wrong_rate_of_confident,
            "uncertain_rate": three.uncertain_rate,
        },
        "forced_binary": {
            "confidently_wrong_rate_of_all": binary.confidently_wrong_rate_of_all,
            "confidently_wrong_rate_of_confident": binary.confidently_wrong_rate_of_confident,
        },
        "grounding": grounding,
        "reviewer_time_saved": time_saved,
        "llm_backend": _llm.name,
    }
