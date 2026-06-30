"""Conversation state for the English School demo.

The state is reconstructed from the full chat_history every turn (the demo is
stateless on the server — the frontend sends the whole history). It is *support*,
not the conversation driver: it seeds the planner with already-known facts and
feeds the guardrail's "don't re-ask a known slot" check.

Deterministic pieces only:
- ``looks_like_contact`` — phone / Telegram detection (handoff safety).
- ``recent_questions_asked`` — which slot the assistant last asked about, so we
  never re-ask it (reused by the guardrail).
- ``apply_planner_updates`` — merges the planner's LLM-extracted slots with
  stable-slot protection and free-text acceptance.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .schemas import ChatHistoryMessage

# ---------------------------------------------------------------------------
# Deterministic detectors (safety only, NOT conversation drivers)
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"\+?\d[\d\s\-\(\)]{6,}\d")
_TELEGRAM_RE = re.compile(r"@\w{3,}")


def looks_like_contact(text: str) -> bool:
    """True if the text contains a phone number or Telegram handle."""
    t = (text or "").strip()
    return bool(_PHONE_RE.search(t) or _TELEGRAM_RE.search(t))


# Phrases the assistant uses when asking about a specific slot. Used to know
# which questions were already asked (so we don't repeat them) — applied both to
# the conversation history and to a freshly generated answer (by the guardrail).
QUESTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("city", ("в каком городе", "каком городе", "какой город")),
    ("district_or_branch", (
        "какой район", "в каком районе", "каком районе", "район удобнее",
        "район или филиал", "какой филиал", "каком филиале", "филиал удобнее",
        "ближайший филиал", "ближайшего филиала", "какой адрес", "адрес удобнее",
        "какая локация", "локация удобнее", "где вам удобнее заниматься",
        "где удобнее заниматься", "где удобно заниматься",
    )),
    ("online_offline", ("онлайн или офлайн", "офлайн или онлайн", "удобнее онлайн", "онлайн или очно")),
    ("target_score", ("какой балл", "целевой балл", "нужен балл", "какой нужен балл")),
    ("exam_date", ("когда планируете", "когда экзамен", "дата экзамена", "когда сдавать", "когда сдаёте")),
    ("level", ("уровень английского", "текущий уровень", "какой уровень", "как оцениваете уровень")),
    ("age", ("сколько лет", "сколько ребёнку", "возраст ребёнк")),
    ("contact", ("имя и номер", "оставьте контакт", "ваш номер", "ваш контакт", "имя и telegram", "имя и whatsapp")),
)


def detect_asked_slots(text: str) -> set[str]:
    """Return the set of slot types a single message asks about."""
    low = (text or "").casefold()
    return {slot for slot, phrases in QUESTION_PATTERNS if any(p in low for p in phrases)}


# Markers for facts already delivered, so the writer can avoid repeating them.
_ANSWERED_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("price_given", ("₸", "тенге")),
    ("trial_offered", ("пробный урок", "пробное занятие")),
    ("contact_requested", ("оставьте", "имя и номер", "ваш контакт")),
    ("diagnostic_offered", ("диагностик",)),
)

# Granular recent-fact markers for no-repeat protection (last 3 assistant turns).
_RECENT_FACT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("group_prices_mentioned", ("58 000", "39 000", "42 000", "45 000", "58000", "39000", "42000", "45000")),
    ("individual_price_mentioned", ("9 500", "72 000", "9500", "72000")),
    ("trial_lesson_mentioned", ("пробный урок", "пробное занятие")),
    ("mini_group_mentioned", ("мини-группа", "4–6", "4-6")),
    ("diagnostic_mentioned", ("диагностик",)),
    # CTA / contact tracking — to suppress repeated offers.
    ("trial_cta_mentioned", (
        "записаться на пробный", "записаться на бесплатный",
        "хотите записаться", "запишитесь", "предлагаю записаться",
    )),
    ("contact_asked", (
        "имя и номер", "оставьте контакт", "ваш номер", "ваш контакт",
        "whatsapp или telegram", "имя и whatsapp", "имя и telegram", "оставьте имя",
    )),
    ("admin_handoff_offered", (
        "передам вопрос", "администратор свяжется", "передать администратору",
        "уточнит администратор", "передам ваш",
    )),
)


def _detect_recent_facts(history: list[ChatHistoryMessage]) -> dict[str, bool]:
    """Scan the last 3 assistant turns for topics already delivered."""
    facts: dict[str, bool] = {
        "group_prices_mentioned": False,
        "individual_price_mentioned": False,
        "all_prices_listed": False,
        "trial_lesson_mentioned": False,
        "mini_group_mentioned": False,
        "diagnostic_mentioned": False,
        "group_vs_individual_explained": False,
        "trial_cta_mentioned": False,
        "contact_asked": False,
        "admin_handoff_offered": False,
    }
    assistant_turns = [m for m in (history or []) if m.role == "assistant"][-3:]
    for msg in assistant_turns:
        content = msg.content or ""
        low = content.casefold()
        for field_name, phrases in _RECENT_FACT_MARKERS:
            if not facts[field_name] and any(p in low for p in phrases):
                facts[field_name] = True
        if not facts["group_vs_individual_explained"] and "групп" in low and "индивидуальн" in low:
            facts["group_vs_individual_explained"] = True
        if not facts["all_prices_listed"] and content.count("₸") >= 4:
            facts["all_prices_listed"] = True
    return facts


def _detect_answered_topics(history: list[ChatHistoryMessage]) -> list[str]:
    topics: list[str] = []
    for msg in (history or [])[-4:]:
        if msg.role != "assistant":
            continue
        low = (msg.content or "").casefold()
        for topic, markers in _ANSWERED_MARKERS:
            if topic not in topics and any(m in low for m in markers):
                topics.append(topic)
    return topics


# ---------------------------------------------------------------------------
# ConversationState
# ---------------------------------------------------------------------------

# Slots the planner may report and that we carry as state. Free-text slots are
# always accepted; the rest are stable (overwrite only on an explicit correction).
SLOT_FIELDS = (
    "program",
    "format_preference",
    "user_role",
    "student_age",
    "current_level",
    "city",
    "preferred_location_text",
    "target_score",
    "exam_date",
    "preferred_schedule",
    "contact",
)
_FREE_TEXT_SLOTS = frozenset({"preferred_location_text", "preferred_schedule", "contact"})
_UNSET = ("", "unknown", None, False)

# Map a "question type" (from detect_asked_slots) to the state field that, when
# already known, means we must not ask that question again.
QUESTION_TO_SLOT: dict[str, str] = {
    "city": "city",
    "district_or_branch": "preferred_location_text",
    "online_offline": "format_preference",
    "target_score": "target_score",
    "exam_date": "exam_date",
    "level": "current_level",
    "age": "student_age",
    "contact": "contact",
}


@dataclass
class ConversationState:
    program: str = "unknown"
    format_preference: str = "unknown"
    user_role: str = "unknown"
    student_age: str = ""
    current_level: str = ""
    city: str = ""
    preferred_location_text: str = ""
    target_score: str = ""
    exam_date: str = ""
    preferred_schedule: str = ""
    contact: str = ""
    recent_topics_answered: list[str] = field(default_factory=list)
    recent_questions_asked: list[str] = field(default_factory=list)
    user_frustration: bool = False
    buyer_stage: str = "info"
    handoff_recommended: bool = False
    # Granular recent-fact tracking (last 3 assistant turns) — no-repeat protection.
    group_prices_mentioned: bool = False
    individual_price_mentioned: bool = False
    all_prices_listed: bool = False
    trial_lesson_mentioned: bool = False
    mini_group_mentioned: bool = False
    diagnostic_mentioned: bool = False
    group_vs_individual_explained: bool = False
    trial_cta_mentioned: bool = False
    contact_asked: bool = False
    admin_handoff_offered: bool = False

    def known_slots(self) -> dict[str, str]:
        """Slots with a concrete, non-empty value."""
        return {
            f: getattr(self, f)
            for f in SLOT_FIELDS
            if getattr(self, f) not in _UNSET
        }

    def is_known(self, slot: str) -> bool:
        return getattr(self, slot, "") not in _UNSET

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


def build_conversation_state(
    history: list[ChatHistoryMessage],
    message: str,
) -> ConversationState:
    """Reconstruct the deterministic seed state from history + current message.

    Only fills what we can detect safely without an LLM: which slot-questions the
    assistant already asked, which facts were already delivered, and any contact
    the user provided. Semantic slots (program, format, city, ...) are filled by
    the planner via ``apply_planner_updates``.
    """
    history = list(history or [])

    questions_asked: list[str] = []
    for msg in history:
        if msg.role == "assistant":
            for slot in detect_asked_slots(msg.content or ""):
                if slot not in questions_asked:
                    questions_asked.append(slot)

    contact = ""
    for msg in history:
        if msg.role == "user" and looks_like_contact(msg.content or ""):
            contact = (msg.content or "").strip()
    if looks_like_contact(message or ""):
        contact = (message or "").strip()

    recent_facts = _detect_recent_facts(history)

    return ConversationState(
        contact=contact,
        recent_topics_answered=_detect_answered_topics(history),
        recent_questions_asked=questions_asked,
        **recent_facts,
    )


def apply_planner_updates(state: ConversationState, planner: dict) -> ConversationState:
    """Merge the planner's slots into state.

    Rules (per spec):
    - Free-text slots are always accepted.
    - Stable non-empty slots are overwritten only when ``planner['correction']``.
    - Empty / unknown planner values never erase existing data.
    """
    correction = bool(planner.get("correction"))
    slots = planner.get("slots") or {}

    for key in SLOT_FIELDS:
        value = slots.get(key)
        if value in _UNSET:
            continue
        if key in _FREE_TEXT_SLOTS:
            setattr(state, key, value)
            continue
        if state.is_known(key) and not correction:
            continue
        setattr(state, key, value)

    buyer_stage = slots.get("buyer_stage")
    if buyer_stage not in _UNSET:
        state.buyer_stage = buyer_stage

    state.user_frustration = bool(planner.get("user_frustration"))
    state.handoff_recommended = bool(planner.get("handoff_recommended"))
    return state
