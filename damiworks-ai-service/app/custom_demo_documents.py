from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock


CUSTOM_DEMO_DOCUMENT_TTL_SECONDS = 24 * 60 * 60
CHUNK_TARGET_SIZE = 1300
CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class CustomDemoChunk:
    document_id: str
    chat_id: str
    filename: str
    chunk_index: int
    text: str


@dataclass(frozen=True)
class CustomDemoDocument:
    document_id: str
    chat_id: str
    filename: str
    chunks: list[CustomDemoChunk]
    created_at: datetime
    expires_at: datetime


_DOCUMENTS_BY_CHAT_ID: dict[str, CustomDemoDocument] = {}
_STORE_LOCK = Lock()


def normalize_document_text(text: str) -> str:
    paragraphs = [
        re.sub(r"[ \t\r\f\v]+", " ", part).strip()
        for part in re.split(r"\n\s*\n+", text or "")
    ]
    paragraphs = [part for part in paragraphs if part]
    if paragraphs:
        return "\n\n".join(paragraphs)
    return re.sub(r"\s+", " ", text or "").strip()


def chunk_document_text(text: str, *, target_size: int = CHUNK_TARGET_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = normalize_document_text(text)
    if not normalized:
        return []

    paragraphs = normalized.split("\n\n")
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > target_size:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + target_size, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                if end >= len(paragraph):
                    break
                start = max(end - overlap, start + 1)
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= target_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    with_overlap: list[str] = []
    for idx, chunk in enumerate(chunks):
        if idx == 0 or not with_overlap:
            with_overlap.append(chunk)
            continue
        previous_tail = with_overlap[-1][-overlap:].strip()
        if previous_tail and previous_tail not in chunk:
            with_overlap.append(f"{previous_tail}\n\n{chunk}".strip())
        else:
            with_overlap.append(chunk)
    return [chunk for chunk in with_overlap if chunk]


def _cleanup_expired(now: float | None = None) -> None:
    ts = now if now is not None else time.time()
    expired = [
        chat_id
        for chat_id, doc in _DOCUMENTS_BY_CHAT_ID.items()
        if doc.expires_at.timestamp() <= ts
    ]
    for chat_id in expired:
        _DOCUMENTS_BY_CHAT_ID.pop(chat_id, None)


def store_custom_demo_document(*, chat_id: str, filename: str, text: str) -> CustomDemoDocument:
    chunks_text = chunk_document_text(text)
    if not chunks_text:
        raise ValueError("empty_document")

    now = datetime.now(timezone.utc)
    document_id = f"doc_{uuid.uuid4().hex[:16]}"
    chunks = [
        CustomDemoChunk(
            document_id=document_id,
            chat_id=chat_id,
            filename=filename,
            chunk_index=idx,
            text=chunk,
        )
        for idx, chunk in enumerate(chunks_text)
    ]
    document = CustomDemoDocument(
        document_id=document_id,
        chat_id=chat_id,
        filename=filename,
        chunks=chunks,
        created_at=now,
        expires_at=now + timedelta(seconds=CUSTOM_DEMO_DOCUMENT_TTL_SECONDS),
    )
    with _STORE_LOCK:
        _cleanup_expired()
        _DOCUMENTS_BY_CHAT_ID[chat_id] = document
    return document


def get_custom_demo_document(chat_id: str) -> CustomDemoDocument | None:
    with _STORE_LOCK:
        _cleanup_expired()
        return _DOCUMENTS_BY_CHAT_ID.get(chat_id)


def clear_custom_demo_documents() -> None:
    with _STORE_LOCK:
        _DOCUMENTS_BY_CHAT_ID.clear()


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\wа-яА-ЯёЁ]{3,}", (text or "").casefold())
        if token
    }


def retrieve_custom_demo_chunks(chat_id: str, query: str, *, max_chunks: int = 5) -> list[CustomDemoChunk]:
    document = get_custom_demo_document(chat_id)
    if not document:
        return []

    query_terms = _terms(query)
    scored: list[tuple[int, int, CustomDemoChunk]] = []
    for chunk in document.chunks:
        chunk_terms = _terms(chunk.text)
        score = len(query_terms & chunk_terms)
        scored.append((score, -chunk.chunk_index, chunk))

    selected: list[CustomDemoChunk] = []
    if not query_terms or all(score == 0 for score, _, _ in scored):
        selected.extend(document.chunks[: min(2, len(document.chunks))])
    else:
        for score, _, chunk in sorted(scored, key=lambda item: (item[0], item[1]), reverse=True):
            if score <= 0:
                continue
            selected.append(chunk)
            if len(selected) >= max_chunks:
                break
        if len(selected) < min(2, len(document.chunks)):
            for chunk in document.chunks[:2]:
                if chunk not in selected:
                    selected.append(chunk)

    return selected[:max_chunks]


def format_custom_demo_document_context(chat_id: str, query: str) -> str:
    document = get_custom_demo_document(chat_id)
    if not document:
        return ""
    chunks = retrieve_custom_demo_chunks(chat_id, query)
    if not chunks:
        return ""
    excerpts = "\n\n".join(
        f"{idx}. {chunk.text}"
        for idx, chunk in enumerate(chunks, start=1)
    )
    return (
        "[UPLOADED BUSINESS DOCUMENT CONTEXT]\n"
        f"Filename: {document.filename}\n\n"
        "Relevant excerpts:\n"
        f"{excerpts}\n"
        "[/UPLOADED BUSINESS DOCUMENT CONTEXT]"
    )
