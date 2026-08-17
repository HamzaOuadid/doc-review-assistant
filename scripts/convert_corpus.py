"""Convert raw SEC EDGAR exhibit HTML/TXT into clean, normalized plain text.

Normalization is deliberately simple and DETERMINISTIC so that citation spans
extracted later are exact substrings of the stored source_text:
  - strip HTML tags (bs4 get_text)
  - collapse runs of whitespace (including newlines) to a single space
  - strip leading/trailing whitespace
This matches the normalization the app's citation.verify_citation() applies,
so "exact source span" checks are meaningful and not defeated by HTML->text
whitespace artifacts.
"""
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

RAW_DIR = Path(sys.argv[1])
OUT_DIR = Path(sys.argv[2])
OUT_DIR.mkdir(parents=True, exist_ok=True)

WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = WS_RE.sub(" ", text)
    return text.strip()


def html_to_text(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ")


for path in sorted(RAW_DIR.iterdir()):
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".htm", ".html"):
        text = html_to_text(raw)
    else:
        text = raw
    clean = normalize(text)
    out_path = OUT_DIR / (path.stem + ".txt")
    out_path.write_text(clean, encoding="utf-8")
    print(f"{path.name:35s} -> {out_path.name:35s} {len(clean):8d} chars")
