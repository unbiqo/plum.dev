"""Conversation state for the Medical Center demo (MedNova Clinic).

The state is reconstructed from the full chat_history every turn (the demo is
stateless on the server — the frontend sends the whole history). It seeds the
planner with already-known facts and feeds the guardrail's "don't re-ask a
known slot" check.

Deterministic pieces only:
- ``looks_like_contact`` — phone / Telegram detection (handoff safety).
- ``detect_red_flags`` — emergency symptom detection. Lives here (not in the
  guardrails module) because both the state builder and the guardrails need it
  and guardrails already imports this module.
- ``recent_questions_asked`` — which slot the assistant last asked about.
- ``apply_planner_updates`` — merges planner slots with stable-slot protection.
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


# Emergency red flags (KB section «Красные флаги»). Strong markers only: a
# routine «побаливает в груди при нагрузке» must NOT trigger — over-triggering
# is safe (the emergency answer is harmless and the next turn resumes the
# normal flow), but the detector should not hijack ordinary booking questions.
_RED_FLAG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("chest_pain", re.compile(
        r"(?:сильн\w+|остр\w+|давящ\w+|жгуч\w+|резк\w+)\s+бол\w+\s+(?:в\s+)?груд"
        r"|бол\w+\s+в\s+груди[^.!?]{0,60}(?:трудно|тяжело|не\s+могу)\s+дыш"
        r"|отда[её]т\s+в\s+(?:лев\w+\s+)?(?:руку|челюсть|лопатку)",
        re.IGNORECASE,
    )),
    ("breathing", re.compile(
        r"(?:не\s+мо(?:гу|жет)|трудно|тяжело)\s+дышать|задыха|одышка\s+в\s+покое|посинел\w*\s+губ",
        re.IGNORECASE,
    )),
    ("stroke", re.compile(
        r"перекосило\s+лицо|перекос\s+лица|асимметри\w+\s+лица"
        r"|онемел[аио]?\s+(?:рука|нога|лицо|половина)"
        r"|слабость\s+в\s+(?:руке|ноге)|невнятн\w+\s+речь|нарушени\w+\s+речи"
        r"|внезапн\w+\s+(?:очень\s+)?сильн\w+\s+головн\w+\s+бол",
        re.IGNORECASE,
    )),
    ("consciousness", re.compile(
        r"потерял[аи]?\s+сознание|без\s+сознания|обморок|судорог",
        re.IGNORECASE,
    )),
    ("bleeding", re.compile(
        r"сильн\w+\s+кровотечени|кровь\s+не\s+останавлива|глубок\w+\s+ран|травм\w+\s+головы",
        re.IGNORECASE,
    )),
    ("infant_fever", re.compile(
        r"(?:младен\w+|груднич\w+|ребёнку?\s+(?:до\s+)?(?:год|месяц|[123]\s*месяц)\w*)[^.!?]{0,60}температур"
        r"|температур\w*[^.!?]{0,60}(?:младен\w+|груднич\w+|до\s+3\s*месяц)"
        r"|реб[ёе]н\w+[^.!?]{0,60}(?:вял\w+|трудно\s+(?:раз)?будить|трудно\s+дышит)"
        r"|(?:вял\w+|трудно\s+(?:раз)?будить)[^.!?]{0,60}реб[ёе]н",
        re.IGNORECASE,
    )),
    ("pregnancy", re.compile(
        r"беремен\w+[^.!?]{0,80}(?:кровотечени|кровянист|кровь|сильн\w+\s+бол|нет\s+шевелени|не\s+чувству\w+\s+шевелени)"
        r"|(?:кровотечени|сильн\w+\s+бол\w+\s+в\s+животе)[^.!?]{0,80}беремен",
        re.IGNORECASE,
    )),
    ("anaphylaxis", re.compile(
        r"от[её]к\s+(?:горла|гортани|лица|языка)|от[её]к\s+квинке|анафилак"
        r"|(?:сыпь|крапивниц\w+)[^.!?]{0,60}(?:задыха|трудно\s+дышать|слабость)",
        re.IGNORECASE,
    )),
    ("high_fever", re.compile(
        r"температур\w*\s+(?:выше\s+)?(?:39[.,]5|40|41)[^%]|ригидность\s+затылка",
        re.IGNORECASE,
    )),
)


def detect_red_flags(text: str) -> str | None:
    """Return the matched red-flag category, or None. First match wins."""
    t = text or ""
    for category, pattern in _RED_FLAG_PATTERNS:
        if pattern.search(t):
            return category
    return None


# Phrases the assistant uses when asking about a specific slot — used to know
# which questions were already asked (so we don't repeat them).
QUESTION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("specialty", (
        "к какому врачу", "какой специалист", "какое направление",
        "к кому хотите", "какой врач нужен",
    )),
    ("age", ("сколько лет", "сколько вам лет", "возраст пациента", "возраст ребёнк", "возраст ребенк")),
    ("symptoms", ("что вас беспокоит", "что беспокоит", "какие жалобы", "опишите жалобы")),
    ("preferred_time", (
        "какое время удобно", "когда удобно", "какой день удобен",
        "удобный день", "на какой день", "какое время вам удобно",
    )),
    ("contact", (
        "имя и номер", "оставьте контакт", "ваш номер", "ваш контакт",
        "whatsapp или telegram", "имя и whatsapp", "имя и telegram", "оставьте имя",
        "ваш whatsapp", "whatsapp/телефон", "телефон для связи",
    )),
)


def detect_asked_slots(text: str) -> set[str]:
    """Return the set of slot types a single message asks about."""
    low = (text or "").casefold()
    return {slot for slot, phrases in QUESTION_PATTERNS if any(p in low for p in phrases)}


# Granular recent-fact markers for no-repeat protection (last 3 assistant turns).
_RECENT_FACT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("prices_mentioned", ("₸", "тенге")),
    ("booking_cta_mentioned", (
        "могу записать", "хотите записаться", "записать вас", "оформим запись",
        "предлагаю записаться", "могу оформить заявку",
    )),
    ("contact_asked", (
        "имя и номер", "оставьте контакт", "ваш номер", "ваш контакт",
        "whatsapp или telegram", "имя и whatsapp", "имя и telegram", "оставьте имя",
        "ваш whatsapp", "whatsapp/телефон", "телефон для связи",
    )),
    ("admin_handoff_offered", (
        "администратор свяжется", "уточнит администратор", "передам заявку",
        "администратор подтвердит", "передам вопрос",
    )),
    ("preparation_mentioned", ("натощак", "подготовк")),
)


def _detect_recent_facts(history: list[ChatHistoryMessage]) -> dict[str, bool]:
    """Scan the last 3 assistant turns for topics already delivered."""
    facts: dict[str, bool] = {
        "prices_mentioned": False,
        "booking_cta_mentioned": False,
        "contact_asked": False,
        "admin_handoff_offered": False,
        "preparation_mentioned": False,
    }
    assistant_turns = [m for m in (history or []) if m.role == "assistant"][-3:]
    for msg in assistant_turns:
        low = (msg.content or "").casefold()
        for field_name, phrases in _RECENT_FACT_MARKERS:
            if not facts[field_name] and any(p in low for p in phrases):
                facts[field_name] = True
    return facts


# ---------------------------------------------------------------------------
# ConversationState
# ---------------------------------------------------------------------------

# Slots the planner may report and that we carry as state. Free-text slots are
# always accepted; the rest are stable (overwrite only on an explicit correction).
SLOT_FIELDS = (
    "patient_name",
    "contact_name",
    "contact",
    "age",
    "specialty",
    "symptoms_or_goal",
    "preferred_time",
)
_FREE_TEXT_SLOTS = frozenset({
    "patient_name", "contact_name", "contact", "symptoms_or_goal", "preferred_time",
})
_UNSET = ("", "unknown", None, False)

# Map a "question type" (from detect_asked_slots) to the state field that, when
# already known, means we must not ask that question again.
QUESTION_TO_SLOT: dict[str, str] = {
    "specialty": "specialty",
    "age": "age",
    "symptoms": "symptoms_or_goal",
    "preferred_time": "preferred_time",
    "contact": "contact",
}


@dataclass
class ConversationState:
    patient_name: str = ""
    contact_name: str = ""
    contact: str = ""
    age: str = ""
    specialty: str = ""
    symptoms_or_goal: str = ""
    preferred_time: str = ""
    # normal -> urgent (planner) -> emergency (red flag; sticky, never downgraded).
    urgency_flag: str = "normal"
    recent_questions_asked: list[str] = field(default_factory=list)
    user_frustration: bool = False
    handoff_recommended: bool = False
    # Recent-fact tracking (last 3 assistant turns) — no-repeat protection.
    prices_mentioned: bool = False
    booking_cta_mentioned: bool = False
    contact_asked: bool = False
    admin_handoff_offered: bool = False
    preparation_mentioned: bool = False
    # True once the assistant has spoken at least once — no repeated greetings.
    greeting_already_sent: bool = False

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

    Only fills what we can detect safely without an LLM: which slot-questions
    the assistant already asked, delivered facts, any contact the user provided,
    and the sticky emergency flag (a red flag anywhere in the user's messages
    keeps the lead marked emergency even if the conversation continues normally).
    """
    history = list(history or [])

    questions_asked: list[str] = []
    for msg in history:
        if msg.role == "assistant":
            for slot in detect_asked_slots(msg.content or ""):
                if slot not in questions_asked:
                    questions_asked.append(slot)

    contact = ""
    urgency_flag = "normal"
    for msg in history:
        if msg.role != "user":
            continue
        if looks_like_contact(msg.content or ""):
            contact = (msg.content or "").strip()
        if urgency_flag != "emergency" and detect_red_flags(msg.content or ""):
            urgency_flag = "emergency"
    if looks_like_contact(message or ""):
        contact = (message or "").strip()
    if detect_red_flags(message or ""):
        urgency_flag = "emergency"

    recent_facts = _detect_recent_facts(history)

    return ConversationState(
        contact=contact,
        urgency_flag=urgency_flag,
        recent_questions_asked=questions_asked,
        greeting_already_sent=any(m.role == "assistant" for m in history),
        **recent_facts,
    )


def apply_planner_updates(state: ConversationState, planner: dict) -> ConversationState:
    """Merge the planner's slots into state.

    Rules:
    - Free-text slots are always accepted.
    - Stable non-empty slots are overwritten only when ``planner['correction']``.
    - Empty / unknown planner values never erase existing data.
    - urgency may be upgraded normal -> urgent by the planner, but emergency
      (set deterministically from red flags) is never downgraded.
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

    urgency = str(slots.get("urgency") or "").strip().lower()
    if urgency == "urgent" and state.urgency_flag == "normal":
        state.urgency_flag = "urgent"

    state.user_frustration = bool(planner.get("user_frustration"))
    state.handoff_recommended = bool(planner.get("handoff_recommended"))
    return state
