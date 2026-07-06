"""Static knowledge base loader for the Medical Center demo (MedNova Clinic).

Mirrors the English School KB mechanism: a markdown file split on ``##``
headings, cached in-memory, and always sent in full (the KB is small). No
vectors, no Supabase — the demo is fully self-contained.
"""

from __future__ import annotations

import re
from pathlib import Path
from threading import Lock

_KB_PATH = Path(__file__).parent / "demo_knowledge" / "medical_center_kz.md"
_CHUNKS: list[dict[str, object]] | None = None
_LOAD_LOCK = Lock()


def _split_into_chunks(text: str) -> list[dict[str, object]]:
    TARGET = 1400
    chunks: list[dict[str, object]] = []

    sections = re.split(r"(?m)^## ", text)
    for section in sections:
        section = section.strip()
        if not section:
            continue

        heading_end = section.find("\n")
        heading = section[:heading_end].strip() if heading_end != -1 else section
        body = section[heading_end:].strip() if heading_end != -1 else ""
        full = f"## {heading}\n\n{body}" if body else f"## {heading}"

        if len(full) <= TARGET:
            chunks.append({"text": full, "heading": heading, "chunk_index": len(chunks)})
            continue

        paragraphs = re.split(r"\n\n+", full)
        current = ""
        for para in paragraphs:
            candidate = f"{current}\n\n{para}".strip() if current else para
            if len(candidate) <= TARGET:
                current = candidate
            else:
                if current:
                    chunks.append({"text": current, "heading": heading, "chunk_index": len(chunks)})
                current = para
        if current:
            chunks.append({"text": current, "heading": heading, "chunk_index": len(chunks)})

    return chunks


def _load_kb() -> list[dict[str, object]]:
    text = _KB_PATH.read_text(encoding="utf-8")
    return _split_into_chunks(text)


def _get_chunks() -> list[dict[str, object]]:
    global _CHUNKS
    if _CHUNKS is None:
        with _LOAD_LOCK:
            if _CHUNKS is None:
                _CHUNKS = _load_kb()
    return _CHUNKS


def get_full_kb_context() -> str:
    """Return the entire knowledge base wrapped as prompt context.

    The KB is small; sending all of it every turn means the writer always has
    every doctor, price and rule, steered by the turn plan.
    """
    return format_kb_context(_get_chunks())


def format_kb_context(chunks: list[dict[str, object]]) -> str:
    if not chunks:
        return ""
    excerpts = "\n\n---\n\n".join(str(chunk["text"]) for chunk in chunks)
    return (
        "[БАЗА ЗНАНИЙ КЛИНИКИ — MedNova Clinic]\n\n"
        f"{excerpts}\n\n"
        "[/БАЗА ЗНАНИЙ КЛИНИКИ]"
    )
