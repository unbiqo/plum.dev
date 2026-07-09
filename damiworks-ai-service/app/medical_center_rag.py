"""Lightweight retrieval layer for the Medical Center (MedNova) knowledge base.

Replaces "send the whole KB every turn" with: a short, always-on ``core``
context (safety-critical sections — red flags, prohibitions, prompt-injection
refusal) plus a small set of query-relevant chunks selected by keyword/alias
scoring (doctors, directions, prices, schedule, availability, licenses,
advantages, routing, FAQ, booking rules, preparation, worked dialogue
scenarios).

This is a local, in-memory, dependency-free index — no embeddings, no
Supabase. DamiWorks' consultant chat has a heavier hybrid vector+keyword RAG
(``SupabaseService.search_knowledge_base`` + ``match_knowledge_hybrid`` RPC),
but that requires per-turn embedding calls and a populated ``rag_documents``
table; medical_center is a self-contained, latency-controlled module (like
english_school) with no existing Supabase/embedding dependency, and the KB is
small enough that a curated local index is simpler and more robust than
bolting the generic vector RPC onto this module's bespoke state-aware scoring
needs (specialty boost, section boost, Russian symptom/specialty aliases).

IMPORTANT: ``medical_center_kb.get_full_kb_context()`` is unchanged and still
used by medical_center_guardrails.py (kb_price_set/kb_doctor_names need to see
every price and every doctor name, regardless of what a given turn retrieves).
This module only affects what gets sent to the planner/writer prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .medical_center_kb import get_raw_markdown
from .medical_center_slots import normalize_specialty, specialty_display
from .schemas import ChatHistoryMessage

# ---------------------------------------------------------------------------
# Chunk model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KbChunk:
    id: str
    title: str
    section: str
    tags: tuple[str, ...]
    text: str
    priority: int = 0


@dataclass
class RetrievedKbContext:
    mode: str
    core_context: str
    chunks: list[KbChunk]
    context: str  # core + selected chunks, ready to inject into the prompt
    query_terms: tuple[str, ...]

    def to_debug_metadata(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "chunk_ids": [c.id for c in self.chunks],
            "chunk_titles": [c.title for c in self.chunks],
            "chunk_count": len(self.chunks),
            "query_terms": list(self.query_terms),
            "core_included": bool(self.core_context),
            "full_kb_injected": False,
        }


# Headings whose content is safety-critical and always included, never subject
# to top-K scoring/selection. Kept short by design.
_CORE_HEADINGS = {
    "Красные флаги — срочная помощь",
    "Защита от посторонних инструкций",
    "Запреты и ограничения ассистента",
}

# Heading -> section type (drives scoring boosts + the debug/log label).
_SECTION_BY_HEADING: dict[str, str] = {
    "Тон администратора": "role_style",
    "О клинике": "services",
    "Направления и услуги": "services",
    "Демо-окна записи": "availability",
    "Лицензии и документы": "licenses",
    "Преимущества клиники": "advantages",
    "Цены": "prices",
    "Пакеты и акции": "prices",
    "Правила записи": "booking_rules",
    "Подготовка к приёмам и анализам": "preparation",
    "Маршрутизация по частым запросам": "routing",
    "Частые вопросы": "faq",
}
# Sections that exist purely as internal reference (lead schema, the frontend's
# own hardcoded first message) — not useful as LLM-facing retrieval content.
_SKIP_HEADINGS = {"Данные для заявки (лид)", "Стартовое сообщение"}

# Canonical specialty -> extra symptom/alias keywords (beyond the specialty
# name itself) used both for chunk tagging and for query-term expansion.
_SPECIALTY_ALIASES: dict[str, tuple[str, ...]] = {
    "терапевт": ("терапевт", "орви", "температура", "давление", "простуда", "взрослый"),
    "педиатр": ("педиатр", "ребенок", "ребёнок", "дети", "сын", "дочь", "детский"),
    "кардиолог": ("кардиолог", "сердце", "сердцебиение", "экг", "давление", "аритми"),
    "эндокринолог": ("эндокринолог", "щитовидка", "щитовидная", "сахар", "гормон", "вес"),
    "гастроэнтеролог": ("гастроэнтеролог", "живот", "жкт", "изжога", "желудок"),
    "невролог": ("невролог", "головная боль", "голова", "спина", "онемение", "головокружение"),
    "лор": ("лор", "оториноларинголог", "ухо", "уши", "горло", "нос", "насморк", "отит", "синусит"),
    "дерматолог": ("дерматолог", "сыпь", "акне", "родинка", "кожа", "зуд"),
    "гинеколог": ("гинеколог", "цикл", "мазок", "беременность"),
    "уролог": ("уролог", "мочеиспускание", "почки", "мочевой"),
    "офтальмолог": ("офтальмолог", "зрение", "глаза", "очки"),
    "стоматолог": ("стоматолог", "зуб", "зубы", "кариес", "дёсны", "десны"),
    "травматолог-ортопед": ("травматолог", "ортопед", "сустав", "колено", "плечо", "травма"),
    "ревматолог": ("ревматолог", "суставы", "скованность", "артрит"),
}
# Non-specialty concept aliases used the same way (query expansion + tagging).
_TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "лицензия": ("лицензия", "лицензии", "документы", "licenses"),
    "цена": ("цена", "цены", "стоимость", "прайс", "сколько стоит"),
    "график": ("график", "расписание", "когда принимает", "приём", "приемные дни"),
    "доступность": ("свободно", "занято", "слот", "окна", "окно", "ближайшее время", "доступ"),
    "преимущества": ("лучше", "преимущества", "почему вы", "чем вы"),
}

_WORD_RE = re.compile(r"[а-яёa-z0-9\-]+", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if len(w) >= 3}


def _doctor_specialty_from_line(first_line: str) -> str | None:
    """Extract the canonical specialty from a doctor bullet's first line."""
    return normalize_specialty(first_line)


# ---------------------------------------------------------------------------
# Parsing: raw markdown -> curated chunks (auto-derived, re-parsed if the KB
# file changes — no hand-maintained duplicate content).
# ---------------------------------------------------------------------------

_DOCTOR_BULLET_RE = re.compile(r"(?m)^- ([А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+) — ")
_DIRECTION_HEADING_RE = re.compile(r"(?m)^### (.+)$")
_SCENARIO_ITEM_RE = re.compile(r"(?m)^(\d+)\.\s+(.+?)(?=^\d+\.\s|\Z)", re.DOTALL)

_CHUNKS: list[KbChunk] | None = None
_CORE: str | None = None
_TEXT_TOKENS: dict[str, frozenset[str]] | None = None


def _split_doctors(body: str) -> list[KbChunk]:
    chunks: list[KbChunk] = []
    matches = list(_DOCTOR_BULLET_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end].strip()
        name = m.group(1)
        first_line = block.split("\n", 1)[0]
        canonical = _doctor_specialty_from_line(first_line)
        disp = specialty_display(canonical) if canonical else ""
        tags = {name.lower(), *name.lower().split(), "врач", "врачи", "специалист", "специалисты", "доктор"}
        if canonical:
            tags.update(_SPECIALTY_ALIASES.get(canonical, (disp,)))
        slug = re.sub(r"[^a-zа-яё0-9]+", "_", name.lower()).strip("_")
        chunks.append(KbChunk(
            id=f"doctor_{slug}",
            title=f"{name} — {disp or 'врач'}",
            section="doctors",
            tags=tuple(tags),
            text=f"- {block}",
            priority=1,
        ))
    return chunks


def _split_directions(body: str) -> list[KbChunk]:
    chunks: list[KbChunk] = []
    parts = _DIRECTION_HEADING_RE.split(body)
    # parts alternates: [preamble, heading1, text1, heading2, text2, ...]
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        canonical = normalize_specialty(heading)
        tags = {heading.lower()}
        if canonical:
            tags.update(_SPECIALTY_ALIASES.get(canonical, ()))
        slug = re.sub(r"[^a-zа-яё0-9]+", "_", heading.lower()).strip("_")
        chunks.append(KbChunk(
            id=f"direction_{slug}",
            title=heading,
            section="services",
            tags=tuple(tags),
            text=f"### {heading}\n{text}",
            priority=1,
        ))
    return chunks


def _split_scenarios(body: str) -> list[KbChunk]:
    chunks: list[KbChunk] = []
    for m in _SCENARIO_ITEM_RE.finditer(body):
        idx, item_text = m.group(1), m.group(2).strip()
        tags = _tokenize(item_text)
        chunks.append(KbChunk(
            id=f"scenario_{idx}",
            title=f"Диалог-пример {idx}",
            section="scenarios",
            tags=tuple(tags),
            text=f"{idx}. {item_text}",
            priority=0,
        ))
    return chunks


def _parse_kb() -> tuple[str, list[KbChunk]]:
    text = get_raw_markdown()
    # Drop the leading "# Title" + one-paragraph disclaimer before the first
    # "## " heading — it's not a retrievable section (the disclaimer's safety
    # content is already covered by the core prohibitions section).
    first_heading = text.find("\n## ")
    if first_heading != -1:
        text = text[first_heading:]
    sections = re.split(r"(?m)^## ", text)
    core_parts: list[str] = []
    chunks: list[KbChunk] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        nl = section.find("\n")
        heading = section[:nl].strip() if nl != -1 else section.strip()
        body = section[nl:].strip() if nl != -1 else ""

        if heading in _SKIP_HEADINGS:
            continue
        if heading in _CORE_HEADINGS:
            core_parts.append(f"## {heading}\n\n{body}")
            continue
        if heading == "Направления — подробно":
            chunks.extend(_split_directions(body))
            continue
        if heading == "Врачи и расписание":
            chunks.extend(_split_doctors(body))
            continue
        if heading == "Примеры диалогов":
            chunks.extend(_split_scenarios(body))
            continue

        section_type = _SECTION_BY_HEADING.get(heading, "faq")
        tags = _tokenize(heading)
        for keywords in _TOPIC_ALIASES.values():
            if any(k in heading.lower() for k in keywords):
                tags.update(keywords)
        slug = re.sub(r"[^a-zа-яё0-9]+", "_", heading.lower()).strip("_")
        chunks.append(KbChunk(
            id=f"section_{slug}",
            title=heading,
            section=section_type,
            tags=tuple(tags) or (heading.lower(),),
            text=f"## {heading}\n\n{body}",
            priority=1 if section_type in ("prices", "licenses", "advantages") else 0,
        ))

    core = (
        "[БАЗА ЗНАНИЙ КЛИНИКИ — ВСЕГДА ДЕЙСТВУЕТ]\n\n"
        + "\n\n---\n\n".join(core_parts)
        + "\n\n[/БАЗА ЗНАНИЙ КЛИНИКИ]"
    )
    return core, chunks


def _get_parsed() -> tuple[str, list[KbChunk], dict[str, frozenset[str]]]:
    global _CORE, _CHUNKS, _TEXT_TOKENS
    if _CHUNKS is None or _CORE is None:
        _CORE, _CHUNKS = _parse_kb()
        _TEXT_TOKENS = {c.id: frozenset(_tokenize(c.text)) for c in _CHUNKS}
    assert _TEXT_TOKENS is not None
    return _CORE, _CHUNKS, _TEXT_TOKENS


# ---------------------------------------------------------------------------
# Scoring + retrieval
# ---------------------------------------------------------------------------

_WRITER_TOP_K = 6
_PLANNER_TOP_K = 4
# Generic fallback shown when nothing scores above zero (e.g. pure smalltalk).
_FALLBACK_CHUNK_IDS = ("section_направления_и_услуги", "section_частые_вопросы")


def _expand_query_terms(raw_tokens: set[str]) -> set[str]:
    """Expand raw tokens through the specialty/topic alias tables so a term
    like "ухо" also activates the "лор" tag family, etc."""
    expanded = set(raw_tokens)
    for canonical, aliases in _SPECIALTY_ALIASES.items():
        if raw_tokens & set(aliases) or canonical in raw_tokens:
            expanded.add(canonical)
            expanded.update(aliases)
    for topic, aliases in _TOPIC_ALIASES.items():
        if raw_tokens & set(aliases) or topic in raw_tokens:
            expanded.add(topic)
            expanded.update(aliases)
    return expanded


# Scenario chunks tag themselves with every word of their own example
# sentence (there's no separate curated keyword list per scenario), so a
# generic conversational word can otherwise make them dominate over concrete
# factual chunks (doctors/prices/directions). They're meant as light tone
# grounding, not primary factual sources — down-weighted accordingly.
_SECTION_WEIGHT: dict[str, float] = {"scenarios": 0.3}


def _score_chunk(
    chunk: KbChunk,
    query_terms: set[str],
    boost_specialty: str | None,
    chunk_text_tokens: dict[str, frozenset[str]],
) -> float:
    """Keyword/tag overlap score. Uses whole-token intersection for the text
    signal (not raw substring containment) — a short query token like "про"
    must not spuriously match inside an unrelated word like "профилактика".
    ``priority`` is a tie-breaker ONLY among chunks that already matched
    something — it must never by itself make an unrelated chunk look relevant
    (that would defeat the no-match fallback and could leak unrelated KB
    content into e.g. a prompt-injection probe)."""
    tag_set = set(chunk.tags)
    base = 2.0 * len(tag_set & query_terms)
    base += 0.5 * len(chunk_text_tokens[chunk.id] & query_terms)
    if boost_specialty and boost_specialty in tag_set:
        base += 3.0
    if base <= 0:
        return 0.0
    base *= _SECTION_WEIGHT.get(chunk.section, 1.0)
    return base + 0.25 * chunk.priority


def retrieve_medical_kb_context(
    *,
    message: str,
    history: list[ChatHistoryMessage],
    specialty: str | None = None,
    symptoms_or_goal: str | None = None,
    mode: str = "writer",
) -> RetrievedKbContext:
    """Select a small set of relevant KB chunks + the always-on core context.

    Query terms come from the current message, the last few user turns
    (not the whole history), and known state (specialty/symptoms) — never the
    full conversation. ``mode="planner"`` returns fewer, compact chunks;
    ``mode="writer"`` returns more, for a fuller answer.
    """
    core, chunks, text_tokens = _get_parsed()

    recent_user_msgs = [m.content or "" for m in (history or []) if m.role == "user"][-3:]
    raw_text = " ".join([*recent_user_msgs, message or "", symptoms_or_goal or ""])
    raw_tokens = _tokenize(raw_text)

    canonical_specialty = normalize_specialty(specialty) if specialty else None
    if canonical_specialty:
        raw_tokens.add(canonical_specialty)

    query_terms = _expand_query_terms(raw_tokens)

    top_k = _PLANNER_TOP_K if mode == "planner" else _WRITER_TOP_K
    scored = [
        (chunk, _score_chunk(chunk, query_terms, canonical_specialty, text_tokens))
        for chunk in chunks
    ]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    selected = [c for c, _ in scored[:top_k]]

    if not selected:
        by_id = {c.id: c for c in chunks}
        selected = [by_id[cid] for cid in _FALLBACK_CHUNK_IDS if cid in by_id]

    body = "\n\n---\n\n".join(c.text for c in selected)
    context = core if not body else f"{core}\n\n---\n\n{body}"

    return RetrievedKbContext(
        mode=mode,
        core_context=core,
        chunks=selected,
        context=context,
        query_terms=tuple(sorted(query_terms)),
    )
