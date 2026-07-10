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
from typing import TYPE_CHECKING

from .medical_center_routing import route_symptom
from .medical_center_slots import (
    match_slot,
    normalize_specialty,
    normalize_symptom_terms,
    specialty_display,
)
from .schemas import ChatHistoryMessage

if TYPE_CHECKING:
    from .medical_center_intake import MedicalIntake

# ---------------------------------------------------------------------------
# Deterministic detectors (safety only, NOT conversation drivers)
# ---------------------------------------------------------------------------

# A phone-shaped run: optional +, then digits with spaces/hyphens/parens.
_PHONE_RE = re.compile(r"\+?\d[\d\s\-\(\)]{4,}\d")
# Telegram in any common form: @handle, t.me/handle, "telegram/тг: handle".
_TELEGRAM_RE = re.compile(
    r"@[a-zA-Z0-9_]{3,}"
    r"|t\.me/[a-zA-Z0-9_]{3,}"
    r"|(?:telegram|телеграм|тг)\b\s*[:\-]?\s*@?[a-zA-Z0-9_]{3,}",
    re.IGNORECASE,
)
# International plausibility: E.164 allows up to 15 digits; 7 is a safe floor.
_PHONE_MIN_DIGITS = 7
_PHONE_MAX_DIGITS = 15


def classify_contact(text: str) -> str:
    """Classify the contact content of a message (country-agnostic).

    Returns ``"telegram"``, ``"phone"``, ``"phone_invalid"`` or ``"none"``.
    A phone is accepted for ANY country: 7–15 digits, with an optional ``+`` and
    spaces/hyphens/parens. A phone-shaped run outside 7–15 digits is
    ``"phone_invalid"``; text with no phone run and no Telegram handle is
    ``"none"``.
    """
    t = (text or "").strip()
    if _TELEGRAM_RE.search(t):
        return "telegram"
    saw_phoneish = False
    for match in _PHONE_RE.finditer(t):
        digit_count = len(re.sub(r"\D", "", match.group(0)))
        if _PHONE_MIN_DIGITS <= digit_count <= _PHONE_MAX_DIGITS:
            return "phone"
        saw_phoneish = True
    return "phone_invalid" if saw_phoneish else "none"


def looks_like_contact(text: str) -> bool:
    """True if the text contains a Telegram handle or a plausible phone number."""
    return classify_contact(text) in ("telegram", "phone")


def extract_contact(text: str) -> str:
    """Return the cleanest contact token from ``text`` (phone or Telegram), or "".

    Prefers a long contiguous digit run (so "Дамир 23 77777102402" -> the phone,
    not the age), then a spaced/formatted phone run, then a Telegram handle.
    """
    t = (text or "").strip()
    tg = _TELEGRAM_RE.search(t)
    if tg:
        return tg.group(0).strip()
    contiguous = re.findall(rf"\d{{{_PHONE_MIN_DIGITS},{_PHONE_MAX_DIGITS}}}", t)
    if contiguous:
        return max(contiguous, key=len)
    for match in _PHONE_RE.finditer(t):
        run = match.group(0).strip()
        if _PHONE_MIN_DIGITS <= len(re.sub(r"\D", "", run)) <= _PHONE_MAX_DIGITS:
            return run
    return ""


# Words that look like a name but are not one, in a booking reply.
_NOT_A_NAME = frozenset({
    "здравствуйте", "привет", "добрый", "день", "вечер", "утро", "спасибо",
    "фио", "имя", "меня", "зовут", "телефон", "номер", "возраст", "лет", "год",
    "года", "мне", "это", "мой", "моя", "да", "нет", "ок", "хорошо", "давайте",
    "записаться", "запись", "whatsapp", "ватсап", "телеграм",
})
_NAME_TOKEN_RE = re.compile(r"\b[А-ЯЁа-яё][А-ЯЁа-яё\-]{1,}\b")
# A standalone 1-3 digit run is an age, not a phone (the phone is stripped first).
_AGE_TOKEN_RE = re.compile(r"\b(\d{1,3})\b")
_AGE_MIN, _AGE_MAX = 1, 120


def extract_booking_fields(text: str) -> dict[str, str]:
    """Deterministically pull name / age / contact out of one booking reply.

    "Дамир 7472438377 23", "Дамир, 23, +77772438377" and "Дамир +7777 23 года"
    all resolve the same way. The planner usually does this, but when it fails
    (or times out) the booking flow used to re-ask for a name the user had
    already given — so this is the deterministic floor under it, never a
    replacement for it (see apply_booking_field_seed).

    The contact is extracted FIRST and removed from the text, so the phone's own
    digits can never be mistaken for an age.
    """
    raw = (text or "").strip()
    if not raw:
        return {}

    fields: dict[str, str] = {}
    contact = extract_contact(raw)
    if contact:
        fields["contact"] = contact
        raw = raw.replace(contact, " ")
    # Strip any remaining phone-shaped run (e.g. a spaced "+7 701 222 33 44"
    # whose canonical token differs from the text) before hunting for the age.
    raw = _PHONE_RE.sub(" ", raw)

    for match in _AGE_TOKEN_RE.finditer(raw):
        value = int(match.group(1))
        if _AGE_MIN <= value <= _AGE_MAX:
            fields["age"] = str(value)
            break

    for match in _NAME_TOKEN_RE.finditer(raw):
        token = match.group(0)
        if token.casefold() in _NOT_A_NAME or len(token) < 2:
            continue
        fields["name"] = token.capitalize()
        break

    return fields


def apply_booking_field_seed(state: ConversationState, message: str) -> ConversationState:
    """Fill name/age/contact from a booking reply, without overwriting the planner.

    Only ever fills slots that are still empty, so an explicit planner value or
    an earlier correction always wins.
    """
    fields = extract_booking_fields(message)
    if not fields:
        return state
    if fields.get("contact") and not state.contact:
        state.contact = fields["contact"]
    if fields.get("age") and not state.is_known("age"):
        state.age = fields["age"]
    name = fields.get("name")
    if name and not (state.patient_name or state.contact_name):
        state.patient_name = name
    return state


def looks_like_invalid_phone(text: str) -> bool:
    """True when the message is clearly a failed contact attempt.

    Only a digit-dominated message whose number is implausible (too long, >15
    digits) — never a valid international number. Ordinary prose that merely
    contains a long id never hijacks the flow.
    """
    if classify_contact(text) != "phone_invalid":
        return False
    t = (text or "").strip()
    digit_count = len(re.sub(r"\D", "", t))
    letter_count = sum(c.isalpha() for c in t)
    return digit_count > _PHONE_MAX_DIGITS and letter_count <= digit_count


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
    # Both word orders: "трудно дышать" and "дышать тяжело" are the same red flag.
    ("breathing", re.compile(
        r"(?:не\s+мо(?:гу|жет)|трудно|тяжело)\s+дыш\w*|дыш\w*\s+(?:трудно|тяжело)"
        r"|задыха|одышка\s+в\s+покое|посинел\w*\s+губ",
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
    ("fever_neck_rash", re.compile(
        r"температур\w*[^.!?]{0,100}(?:сыпь|ше[яюи]\s+не\s+(?:сгиба|гн[её]т)|скованн\w+\s+(?:в\s+)?ше[еи])"
        r"|(?:сыпь|ше[яюи]\s+не\s+(?:сгиба|гн[её]т)|скованн\w+\s+(?:в\s+)?ше[еи])[^.!?]{0,100}температур\w*",
        re.IGNORECASE,
    )),
    # Acute joint/limb trauma that needs urgent care (fracture/infection signs).
    # Deliberately narrow — plain «колено опухло» must NOT trigger.
    ("joint_trauma", re.compile(
        r"не\s+могу\s+(?:наступить|встать)\s+на\s+ногу|невозможно\s+наступить"
        r"|деформ\w+\s+(?:сустав|колен|ног|стоп)|(?:сустав|колен|нога|стопа)\w*\s+деформ"
        r"|сильн\w+\s+от[её]к\w*\s+после\s+(?:травм|удар|падени)"
        r"|(?:сустав|колен)\w*\s+горяч\w+[^.!?]{0,40}температур"
        r"|температур\w*[^.!?]{0,40}(?:сустав|колен)\w*\s+горяч",
        re.IGNORECASE,
    )),
    # Calf/leg discomfort combined with breathing/chest-pain, or a sudden
    # asymmetric swelling — the classic urgent-care combination. Deliberately
    # narrow: bare calf discomfort alone (no breathing/swelling clue) must NOT
    # trigger here — it goes through the generic intake safety screen instead
    # (medical_center_intake.py / medical_center_demo.py).
    ("leg_swelling_emergency", re.compile(
        r"(?:икр\w*|голен(?!остоп)\w*)[^.!?]{0,60}(?:одышк\w*|тяжело\s+дыш\w*|трудно\s+дыш\w*|боль\w*\s+в\s+груди)"
        r"|(?:одышк\w*|тяжело\s+дыш\w*|трудно\s+дыш\w*|боль\w*\s+в\s+груди)[^.!?]{0,60}(?:икр\w*|голен(?!остоп)\w*)"
        r"|сильн\w+\s+от[её]к\w*\s+(?:на\s+)?одной\s+ноги|от[её]к\w*\s+(?:на\s+)?одной\s+ноги",
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


# Symptom -> specialty routing (KB specialties only).
# Deterministic and routing-only — never a diagnosis. Used solely by the safe
# fallback so a degraded-LLM turn still guides the patient to a specialist and
# asks a clarifying question instead of dumping to the administrator. Patterns
# use symptom words, never specialty names, so a price question like
# «сколько стоит приём невролога» does NOT match.
_SYMPTOM_SPECIALTY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bзуб\w*|дёсн\w*|десн\w*|карие[сc]|пломб", re.IGNORECASE),
     "стоматолог"),
    (re.compile(r"живот|желуд|изжог|тошнот|отрыжк|вздути|стул|понос|запор|кишечник|\bжкт\b", re.IGNORECASE),
     "гастроэнтеролог или терапевт"),
    (re.compile(r"спин|поясниц|\bшея\b|\bшею\b|\bшеи\b|онемен|головокруж|мигрен|голов[ае]\s+бол|болит\s+голов", re.IGNORECASE),
     "невролог"),
    (re.compile(r"сердц|давлени[ея]|сердцебиени|аритми|пульс", re.IGNORECASE),
     "кардиолог"),
    (re.compile(r"\bгорло|\bухо\b|\bуши\b|\bнос\b|насморк|гаймор|синусит|\bотит|слух", re.IGNORECASE),
     "ЛОР"),
    (re.compile(r"\bкож|сыпь|высыпани|\bпрыщ|\bакне|родинк|\bзуд|дерматит|грибок", re.IGNORECASE),
     "дерматолог"),
    (re.compile(r"\bглаз|зрени|\bочк[иов]", re.IGNORECASE),
     "офтальмолог"),
    (re.compile(r"щитовид|сахар|гормон|\bвес\b|похуде|набор\s+веса", re.IGNORECASE),
     "эндокринолог"),
    (re.compile(r"мочеиспуск|мочев|мочит|цистит", re.IGNORECASE),
     "уролог"),
    (re.compile(r"температур|\bорви\b|простуд|кашель|насморк|слабость|ломота", re.IGNORECASE),
     "терапевт (для ребёнка — педиатр)"),
)


def detect_symptom_specialty(text: str) -> str | None:
    """Return a routing phrase (which specialist usually handles this), or None.

    Routing only — never a diagnosis. Musculoskeletal / joint / nerve complaints
    go through the deterministic routing table first (so knee pain lands on
    травматолог-ортопед, not the LLM's guess); the rest use the local patterns.
    """
    routed = route_symptom(text)
    if routed:
        return routed.specialty
    t = text or ""
    for pattern, specialty in _SYMPTOM_SPECIALTY_PATTERNS:
        if pattern.search(t):
            return specialty
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
        "ваш whatsapp", "whatsapp/телефон", "телефон для связи", "пришлите, пожалуйста: фио",
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
        "ваш whatsapp", "whatsapp/телефон", "телефон для связи", "пришлите, пожалуйста: фио",
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
    # Structured understanding of the complaint (medical_center_intake.py).
    # Deliberately NOT in SLOT_FIELDS: the planner neither reports nor overwrites
    # these — they are derived deterministically from the transcript every turn,
    # so the summary panel keeps showing the complaint even when the planner
    # returns nothing for symptoms_or_goal.
    complaint_type: str = ""
    body_part: str = ""
    child_case: bool = False
    self_patient: str = "unknown"  # "true" | "false" | "unknown"
    # The concrete demo slot the user picked (e.g. "завтра 15:30"). Set
    # deterministically from the controlled demo availability, never by the LLM.
    selected_slot: str = ""
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
            contact = extract_contact(msg.content or "")
        if urgency_flag != "emergency" and detect_red_flags(msg.content or ""):
            urgency_flag = "emergency"
    if looks_like_contact(message or ""):
        contact = extract_contact(message or "")
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


# The demo server is stateless (the frontend replays the whole history each
# turn), so specialty and the picked slot must be reconstructed from history.
# The assistant always echoes a picked slot as "<день> ЧЧ:ММ к <врачу>"
# («Отлично, завтра 16:00 к ЛОРу», «Хорошо, выбрали послезавтра 12:00 к ЛОРу»,
# «Записали вас на … к …»). The multi-slot offer never has "к" after a time.
# A slot label is either a relative day ("завтра") or a weekday ("вторник"),
# because a user who asks for a weekday gets weekday-labelled windows back.
_SLOT_DAY_ALT = (
    r"послезавтра|завтра|сегодня"
    r"|понедельник|вторник|сред[уа]|четверг|пятниц[уа]|суббот[уа]|воскресенье"
)
_CONFIRMED_SLOT_RE = re.compile(
    rf"({_SLOT_DAY_ALT})\s+(\d{{1,2}}:\d{{2}})\s+к\b",
    re.IGNORECASE,
)
# The system's OWN committed-routing/booking text always names a specialty right
# after "к"/"ко" ("к терапевту", "К ЛОРу", "к травматологу-ортопеду" — see
# _CONFIRMED_SLOT_RE above and every offer/confirm string in medical_center_demo.py
# / medical_center_routing.py). Gating on this pattern, AND scanning only the
# assistant's own messages, avoids two failure modes: (1) picking up a specialty
# FIELD name that merely appears inside a generic sentence like a services list
# (e.g. "терапевт, педиатр, кардиолог..." previously misread as a chosen
# specialty via naive substring search over the whole sentence), and (2) ever
# treating the user's own objection/negation ("Почему педиатра?", "Только не к
# педиатру") as if they had chosen that specialty — those are user messages and
# are never scanned by this function.
_SPECIALTY_MENTION_RE = re.compile(
    r"(?:^|[^а-яё])ко?[ \t]+([а-яё][а-яё\-]{2,})",
    re.IGNORECASE,
)
# The assistant's "Правильно понял, хотите X?" clarification proposes a slot.
_SUGGEST_SLOT_RE = re.compile(
    rf"хотите\s+({_SLOT_DAY_ALT})\s+(?:в\s+)?(\d{{1,2}}:\d{{2}})",
    re.IGNORECASE,
)
_AFFIRMATION_RE = re.compile(
    r"^\W*(?:да|ага|угу|ок(?:ей)?|okay|ok|yes|верно|правильно|точно|именно|"
    r"хорошо|давай(?:те)?|подходит|подойд[её]т|годится|согласен|согласна)\b",
    re.IGNORECASE,
)


def is_affirmation(text: str) -> bool:
    """True if the message is a short yes/agreement (used to confirm a suggestion)."""
    return bool(_AFFIRMATION_RE.match((text or "").strip()))


def reconstruct_specialty_from_history(history: list[ChatHistoryMessage]) -> str:
    """Most recently NAMED specialty in the conversation (RU display), or "".

    Fallback for when the current planner call did not fill specialty (e.g. an
    LLM timeout) — the deterministic booking flow still needs to know it. Only
    trusts the ASSISTANT's own prior "к <specialty>" / "ко <specialty>" phrasing
    — the grammatical pattern the system's own text always uses when a specialty
    is genuinely established (route/offer/confirm). A generic sentence merely
    listing services, or the user's own objection/negation, will not match —
    see module note above on _SPECIALTY_MENTION_RE for why this is both
    false-positive-safe and negation-safe.

    A HEDGED mention ("обычно обращаются к травматологу-ортопеду или терапевту")
    is not a committed routing decision — it's the writer naming two possible
    options, not confirming one. Skip any match immediately followed by "или"
    (an alternative) instead of locking onto whichever specialty happens to be
    named first.
    """
    for msg in reversed(list(history or [])):
        if msg.role != "assistant":
            continue
        content = msg.content or ""
        for m in reversed(list(_SPECIALTY_MENTION_RE.finditer(content))):
            tail = content[m.end():m.end() + 40]
            if re.match(r"\s*или\b", tail, re.IGNORECASE):
                continue
            canonical = normalize_specialty(m.group(1))
            if canonical:
                return specialty_display(canonical)
    return ""


def reconstruct_selected_slot(
    history: list[ChatHistoryMessage],
    message: str,
    specialty: str,
) -> str:
    """The demo slot the user has already picked, recovered from history.

    A slot is confirmed by a confident match, by the assistant echoing it back,
    or by the user affirming ("да") a "Правильно понял, хотите X?" suggestion.
    A phone number is never parsed for a slot. The latest confirmation wins.
    """
    if not specialty:
        return ""
    latest = ""
    pending_suggestion = ""  # slot the assistant last proposed, awaiting a yes
    for msg in list(history or []):
        content = msg.content or ""
        if msg.role == "user":
            if classify_contact(content) == "phone":
                continue  # a phone reply is not a slot selection
            got = match_slot(specialty, content)
            if got:
                latest = got
                pending_suggestion = ""
            elif pending_suggestion and is_affirmation(content):
                latest = pending_suggestion
                pending_suggestion = ""
        else:
            cm = _CONFIRMED_SLOT_RE.search(content)
            if cm:
                latest = f"{cm.group(1).lower()} {cm.group(2)}"
                pending_suggestion = ""
            sm = _SUGGEST_SLOT_RE.search(content)
            if sm:
                pending_suggestion = f"{sm.group(1).lower()} {sm.group(2)}"

    if classify_contact(message or "") != "phone":
        got = match_slot(specialty, message or "")
        if got:
            latest = got
        elif pending_suggestion and is_affirmation(message or ""):
            latest = pending_suggestion
    return latest


def apply_intake_seed(state: ConversationState, intake: "MedicalIntake") -> ConversationState:
    """Seed the state with the deterministically understood complaint.

    Runs before the planner, so every turn (including the short-circuits that
    never call an LLM) carries the complaint into metadata and the summary panel.
    ``symptoms_or_goal`` is only seeded when empty — a later planner value or a
    routing rule's own complaint label is more specific and must win.
    """
    if not intake.is_medical_complaint:
        return state
    if not state.symptoms_or_goal:
        state.symptoms_or_goal = intake.symptoms_or_goal
    state.complaint_type = intake.complaint_type
    state.body_part = intake.body_part
    state.child_case = intake.child_case
    state.self_patient = "true" if intake.self_patient else "false"
    return state


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
        # RU-normalize known values so the summary panel never shows English.
        if key == "specialty":
            # KB-bound: the planner may only name a specialty MedNova actually
            # has. An unknown one is dropped rather than written into state,
            # so the booking flow can never offer slots for a doctor who does
            # not exist (it refuses to run without a specialty).
            if not normalize_specialty(value):
                continue
            value = specialty_display(value)
        elif key == "symptoms_or_goal":
            value = normalize_symptom_terms(value) or value
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
