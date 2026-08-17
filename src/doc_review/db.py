"""SQLite persistence for the spec's data model: documents / extractions /
hand_labels. SQLite (not Postgres) -- no Docker daemon needed, works
identically in CI and locally, and this project's scale (a few dozen
documents, a few hundred extractions) doesn't need more.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from doc_review.models import Document, Extraction, HandLabel

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id),
    field_name TEXT NOT NULL,
    extracted_value TEXT,
    citation_span TEXT,
    classification TEXT NOT NULL CHECK (classification IN ('include', 'exclude', 'uncertain')),
    reason TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    grounded INTEGER NOT NULL DEFAULT 0,
    backend TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS hand_labels (
    document_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    correct_classification TEXT NOT NULL CHECK (correct_classification IN ('include', 'exclude', 'uncertain')),
    correct_value TEXT,
    citation_span TEXT,
    reason TEXT,
    PRIMARY KEY (document_id, field_name)
);
"""


@contextmanager
def connect(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_document(db_path: str, document: Document) -> None:
    import json

    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents (id, source_text, metadata) VALUES (?, ?, ?)",
            (document.id, document.source_text, json.dumps(document.metadata)),
        )


def insert_extractions(db_path: str, extractions: list[Extraction]) -> None:
    if not extractions:
        return
    doc_ids = sorted({e.document_id for e in extractions})
    with connect(db_path) as conn:
        placeholders = ",".join("?" * len(doc_ids))
        conn.execute(f"DELETE FROM extractions WHERE document_id IN ({placeholders})", doc_ids)
        conn.executemany(
            """INSERT INTO extractions
               (document_id, field_name, extracted_value, citation_span, classification, reason, confidence, grounded, backend)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    e.document_id, e.field_name, e.extracted_value, e.citation_span,
                    e.classification, e.reason, e.confidence, int(e.grounded), e.backend,
                )
                for e in extractions
            ],
        )


def get_extractions(db_path: str, document_id: str | None = None) -> list[Extraction]:
    with connect(db_path) as conn:
        if document_id:
            rows = conn.execute("SELECT * FROM extractions WHERE document_id = ?", (document_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM extractions").fetchall()
    return [
        Extraction(
            document_id=r["document_id"], field_name=r["field_name"],
            extracted_value=r["extracted_value"], citation_span=r["citation_span"],
            classification=r["classification"], reason=r["reason"],
            confidence=r["confidence"], grounded=bool(r["grounded"]), backend=r["backend"],
        )
        for r in rows
    ]


def insert_hand_labels(db_path: str, labels: list[HandLabel]) -> None:
    with connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO hand_labels
               (document_id, field_name, correct_classification, correct_value, citation_span, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (l.document_id, l.field_name, l.correct_classification, l.correct_value, l.citation_span, l.reason)
                for l in labels
            ],
        )
