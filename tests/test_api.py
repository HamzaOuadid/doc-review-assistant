"""Smoke tests for the FastAPI surface (extract / classify / verify_citation
per the spec's API contract, plus /evaluate)."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Isolate the DB per test run so tests don't fight over doc_review.db.
    tmp_db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("DB_PATH", tmp_db)
    from doc_review.config import settings

    settings.db_path = tmp_db
    from doc_review import api

    api.settings.db_path = tmp_db
    with TestClient(api.app) as c:
        yield c
    if os.path.exists(tmp_db):
        os.remove(tmp_db)


def test_verify_citation_endpoint_grounded(client):
    resp = client.post("/verify_citation", json={"span": "hello world", "document": "well, hello world indeed"})
    assert resp.status_code == 200
    assert resp.json() == {"grounded": True}


def test_verify_citation_endpoint_hallucinated(client):
    resp = client.post("/verify_citation", json={"span": "totally fabricated text", "document": "unrelated content"})
    assert resp.status_code == 200
    assert resp.json() == {"grounded": False}


def test_extract_endpoint_returns_all_schema_fields(client):
    doc_text = (
        "This Master Services Agreement is entered into as of March 1, 2022 "
        '(the "Effective Date"). This Agreement shall be governed by the laws '
        "of the State of Texas. Termination for Convenience. Either party may "
        "terminate for convenience upon notice. Confidentiality. Each party "
        "shall protect Confidential Information."
    )
    resp = client.post("/extract", json={"document_id": "api_test_doc", "source_text": doc_text})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 6  # MSA_REVIEW_SCHEMA field count
    for r in results:
        assert r["classification"] in ("include", "exclude", "uncertain")
        if r["classification"] == "include":
            assert r["grounded"] is True


def test_get_extractions_after_extract(client):
    client.post("/extract", json={"document_id": "doc2", "source_text": "Nothing relevant in here at all."})
    resp = client.get("/documents/doc2/extractions")
    assert resp.status_code == 200
    assert len(resp.json()) == 6


def test_get_extractions_for_unknown_document_is_404(client):
    resp = client.get("/documents/does-not-exist/extractions")
    assert resp.status_code == 404


def test_evaluate_endpoint_returns_metrics(client):
    resp = client.get("/evaluate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_documents"] == 12
    assert "three_state" in body and "forced_binary" in body
    assert "reviewer_time_saved" in body
