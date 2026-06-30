from __future__ import annotations

import re
from pathlib import Path
from threading import Lock

_KB_PATH = Path(__file__).parent / "demo_knowledge" / "english_school_kz.md"
_CHUNKS: list[dict[str, object]] | None = None
_LOAD_LOCK = Lock()

_PRICING_QUERY_KEYWORDS = frozenset([
    "сколько", "стоит", "цена", "стоимость", "прайс", "тенге", "₸",
    "индивидуальн", "личн", "групповы", "онлайн", "занятие", "месяц",
    "price", "cost", "individual", "private", "group", "monthly",
])

_PRICING_CHUNK_MARKERS = (
    "₸", "тенге", "за занятие", "в месяц", "стоимость", "цены",
    "индивидуальные", "групповые", "39 000", "42 000", "45 000",
    "58 000", "9 500", "15 000", "72 000",
)

_INDIVIDUAL_CHUNK_MARKERS = (
    "индивидуальн",
    "9 500",
    "один на один",
    "персональн",
    "individual lessons",
    "личных занятий",
    "личное занятие",
)

_BROAD_QUERY_RE = re.compile(
    r"расскаж|что\s+(?:у вас|вы\s+пред|есть|нужно)|какие\s+(?:услуги|программ|формат|курс)|"
    r"что\s+(?:могу|можно)|как\s+(?:проход|устроен|работа)|самое\s+главное|"
    r"про\s+компани|про\s+школ|что\s+(?:предлаг|у\s+вас)|расскажи",
    re.IGNORECASE,
)


def _terms(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[\wа-яА-ЯёЁ₸]{3,}", (text or "").casefold())
        if tok
    }


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


def _is_pricing_query(query: str) -> bool:
    q = query.casefold()
    return any(kw in q for kw in _PRICING_QUERY_KEYWORDS)


def _chunk_has_pricing(chunk_text: str) -> bool:
    ct = chunk_text.casefold()
    return any(marker in ct for marker in _PRICING_CHUNK_MARKERS)


def _chunk_is_individual_focused(chunk_text: str) -> bool:
    ct = chunk_text.casefold()
    return any(marker in ct for marker in _INDIVIDUAL_CHUNK_MARKERS)


def _is_broad_query(query: str) -> bool:
    return bool(_BROAD_QUERY_RE.search(query))


def retrieve_chunks(query: str, top_k: int = 6, active_format: str = "unknown") -> list[dict[str, object]]:
    chunks = _get_chunks()
    if not chunks:
        return []

    query_terms = _terms(query)
    is_pricing = _is_pricing_query(query)
    is_broad = _is_broad_query(query) or not query_terms
    is_individual_context = active_format == "individual"

    scored: list[tuple[int, int, dict[str, object]]] = []
    for chunk in chunks:
        chunk_text = str(chunk["text"])
        chunk_terms = _terms(chunk_text)
        score = len(query_terms & chunk_terms)
        if is_pricing and _chunk_has_pricing(chunk_text):
            score += 3
        if is_individual_context and _chunk_is_individual_focused(chunk_text):
            score += 3
        scored.append((score, -int(chunk["chunk_index"]), chunk))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    selected: list[dict[str, object]] = []
    first_chunk = chunks[0]
    pricing_chunk = next(
        (c for c in chunks if "цены и условия" in str(c.get("heading", "")).casefold()),
        None,
    )
    programs_chunk = next(
        (c for c in chunks if "программы" in str(c.get("heading", "")).casefold()),
        None,
    )
    individual_chunk = next(
        (c for c in chunks if _chunk_is_individual_focused(str(c["text"]))),
        None,
    )

    for _, _, chunk in scored:
        if len(selected) >= top_k:
            break
        if chunk not in selected:
            selected.append(chunk)

    # For broad questions, always include overview + programs + pricing
    if is_broad:
        for pinned in filter(None, [first_chunk, programs_chunk, pricing_chunk]):
            if pinned not in selected:
                selected.insert(0, pinned)

    # For pricing questions, always include the pricing chunk
    if is_pricing and pricing_chunk and pricing_chunk not in selected:
        selected.insert(0, pricing_chunk)

    # For individual context, always include individual-focused chunk
    if is_individual_context and individual_chunk and individual_chunk not in selected:
        selected.insert(0, individual_chunk)

    # Deduplicate preserving order
    seen: set[int] = set()
    deduped: list[dict[str, object]] = []
    for chunk in selected:
        idx = int(chunk["chunk_index"])
        if idx not in seen:
            seen.add(idx)
            deduped.append(chunk)

    return deduped[:top_k]


def get_full_kb_context() -> str:
    """Return the entire knowledge base wrapped as prompt context.

    The KB is small (~13 chunks). Sending all of it every turn removes the
    wrong-chunk-pinning failure mode entirely — the LLM always has every
    program's price/format/audience and is steered by the focus instruction.
    """
    return format_kb_context(_get_chunks())


def format_kb_context(chunks: list[dict[str, object]]) -> str:
    if not chunks:
        return ""
    excerpts = "\n\n---\n\n".join(str(chunk["text"]) for chunk in chunks)
    return (
        "[БАЗА ЗНАНИЙ ШКОЛЫ — Alem English Academy]\n\n"
        f"{excerpts}\n\n"
        "[/БАЗА ЗНАНИЙ ШКОЛЫ]"
    )
