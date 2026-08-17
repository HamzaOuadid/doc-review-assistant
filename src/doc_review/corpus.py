"""Loads the real document corpus and its hand-labeled ground truth.

The corpus (fixtures/corpus/*.txt) is twelve real Master Services
Agreements pulled from public SEC EDGAR exhibit filings -- see
scripts/convert_corpus.py for how the raw HTML/TXT filings were cleaned,
and scripts/build_hand_labels.py for how fixtures/hand_labels.json's exact
citation spans were sliced (never hand-retyped) straight out of these
same files.
"""
import json
from pathlib import Path

from doc_review.config import settings
from doc_review.models import Document, HandLabel


def load_corpus(corpus_dir: str | None = None) -> list[Document]:
    directory = Path(corpus_dir or settings.corpus_dir)
    documents = []
    for path in sorted(directory.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        documents.append(Document(id=path.stem, source_text=text, metadata={"source_file": path.name}))
    return documents


def load_hand_labels(path: str | None = None) -> list[HandLabel]:
    labels_path = Path(path or settings.hand_labels_path)
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    return [HandLabel(**record) for record in data]
