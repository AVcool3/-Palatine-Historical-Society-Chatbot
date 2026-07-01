"""Load every document in the data folders, split into chunks, and build a
searchable index saved as JSON.

Run directly to (re)build the index:

    python -m src.ingest
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

import config


@dataclass
class Chunk:
    """A retrievable slice of a source document."""

    doc_id: str          # relative path of the source file
    source: str          # human-friendly source label
    title: str           # document title (first heading or filename)
    text: str            # the chunk text
    chunk_index: int     # position within the document


# --------------------------------------------------------------------------
# Reading files
# --------------------------------------------------------------------------
def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"  ! Skipping PDF (install 'pypdf' to read it): {path.name}", file=sys.stderr)
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pragma: no cover
        print(f"  ! Could not read PDF {path.name}: {exc}", file=sys.stderr)
        return ""


def _read_document(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in config.PDF_EXTENSIONS:
        return _read_pdf(path)
    if ext in config.TEXT_EXTENSIONS:
        return _read_text_file(path)
    return ""


def _title_for(path: Path, text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
        if line:
            return line[:80]
    return path.stem.replace("_", " ").title()


def _source_label(path: Path) -> str:
    try:
        rel = path.relative_to(config.DATA_DIR)
    except ValueError:
        return path.name
    top = rel.parts[0] if rel.parts else ""
    return {
        "historical_records": "Historical record",
        "historical_society": "Palatine Historical Society (scraped)",
        "my_documents": "Your document",
    }.get(top, top)


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------
def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
    """Split text into ~`size`-char chunks, breaking on paragraph boundaries
    where possible and overlapping consecutive chunks by `overlap` chars."""
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) <= size:
                current = para
            else:
                # Paragraph itself too big: hard-split it.
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
                current = ""
    if current:
        chunks.append(current)

    # Add overlap between adjacent chunks for context continuity.
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for prev, nxt in zip(chunks, chunks[1:]):
            tail = prev[-overlap:]
            overlapped.append(f"{tail}\n\n{nxt}")
        chunks = overlapped
    return chunks


# --------------------------------------------------------------------------
# Index building
# --------------------------------------------------------------------------
def _iter_source_files() -> Iterable[Path]:
    exts = config.TEXT_EXTENSIONS | config.PDF_EXTENSIONS
    for base in config.CONTENT_DIRS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
            # Skip our own README/helper files from the *_documents* folders? No —
            # they contain useful guidance, but skip obvious noise:
            if path.name in {"search_index.json"}:
                continue
            yield path


def build_index() -> List[Chunk]:
    chunks: List[Chunk] = []
    n_docs = 0
    for path in _iter_source_files():
        text = _read_document(path)
        if not text.strip():
            continue
        n_docs += 1
        doc_id = str(path.relative_to(config.ROOT))
        title = _title_for(path, text)
        source = _source_label(path)
        for i, piece in enumerate(_chunk_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)):
            chunks.append(Chunk(doc_id=doc_id, source=source, title=title, text=piece, chunk_index=i))
    print(f"Indexed {len(chunks)} chunks from {n_docs} documents.")
    return chunks


def save_index(chunks: List[Chunk]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "chunks": [asdict(c) for c in chunks]}
    config.INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved index -> {config.INDEX_PATH}")


def load_index() -> List[Chunk]:
    if not config.INDEX_PATH.exists():
        return []
    data = json.loads(config.INDEX_PATH.read_text(encoding="utf-8"))
    return [Chunk(**c) for c in data.get("chunks", [])]


def main() -> None:
    chunks = build_index()
    save_index(chunks)


if __name__ == "__main__":
    main()
