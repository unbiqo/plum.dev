"""Medical Center demo agent (MedNova Clinic) — LLM-first conversational assistant.

Public entrypoint for ``instance_id == "damiworks_medical_center_demo"``.

Pipeline (LLM understands the conversation; code protects the patient and the
business process):

    build_conversation_state  (deterministic seed, incl. sticky urgency)
        -> EMERGENCY SHORT-CIRCUIT (red flag in the current message: fixed safe
           answer, ZERO LLM calls, no booking CTA)
        -> plan_conversation_turn   (LLM JSON planner, temp 0)
        -> apply_planner_updates    (state merge, slot protection)
        -> write_response           (LLM writer, temp 0.35)
        -> validate_answer          (deterministic medical guardrails)
        -> [one repair if it failed] -> [intent-aware safe fallback if still bad]

Each LLM call is wrapped with asyncio.wait_for. A timeout degrades gracefully.
Never a 500.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from .medical_center_guardrails import (
    EMERGENCY_ANSWER,
    build_safe_fallback,
    validate_answer,
)
from .medical_center_intake import (
    assistant_asked_safety_screen,
    build_routing_answer,
    build_safety_question,
    extract_conversation_intake,
    extract_medical_intake,
    is_filler_reply,
    needs_safety_screen,
    specialty_for_intake,
)
from .medical_center_rag import retrieve_medical_kb_context
from .medical_center_planner import (
    plan_conversation_turn,
    reclassify_discount_question,
    reclassify_medical_advice_question,
)
from .medical_center_routing import route_symptom
from .medical_center_schedule import (
    WEEKDAY_ACCUSATIVE,
    WEEKDAY_NOMINATIVE as _WEEKDAY_NOMINATIVE,
    hours_on,
    schedule_sentence,
    time_within_schedule,
    weekday_from_text,
    windows_on,
    working_days_sentence,
    works_on,
)
from .medical_center_slots import (
    format_slots,
    resolve_slot,
    slots_for,
    specialty_dative,
)
from .booking_guardrail import enforce_slot_guardrail
from .medical_center_state import (
    ConversationState,
    apply_booking_field_seed,
    apply_intake_seed,
    apply_planner_updates,
    build_conversation_state,
    detect_red_flags,
    detect_symptom_specialty,
    is_affirmation,
    looks_like_contact,
    looks_like_invalid_phone,
    reconstruct_selected_slot,
    reconstruct_specialty_from_history,
)
from .medical_center_writer import write_response
from .schemas import ChatHistoryMessage, ChatResponse, Route

if TYPE_CHECKING:
    from .gemini_service import GeminiService
    from .schemas import ChatRequest

logger = logging.getLogger(__name__)

MEDICAL_CENTER_INSTANCE_ID = "damiworks_medical_center_demo"

# Deterministic reply when we can't find a usable contact. Country-agnostic —
# never says "usually 11 digits" (that is wrong for international users).
INVALID_CONTACT_ANSWER = (
    "Не вижу контакт для связи. Оставьте, пожалуйста, телефон в любом "
    "международном формате или Telegram."
)

# Single source of truth for the patient-facing clinic address.
CLINIC_ADDRESS_ANSWER = (
    "MedNova Clinic находится в Астане, по адресу: проспект Тауелсиздик, 33."
)

# Deterministic deflection for prompt-injection / internal-architecture probes.
# Matches the KB's own "Защита от посторонних инструкций" wording so the
# behavior is consistent whether this short-circuit or the LLM (grounded on
# that KB section) ends up answering. A dedicated CODE short-circuit is more
# robust than relying on retrieval to surface the right chunk for an
# adversarial prompt specifically designed to evade instructions.
INJECTION_REFUSAL_ANSWER = (
    "Я могу помочь только с вопросами по клинике: услуги, врачи, цены, график "
    "и запись. Хотите подобрать специалиста?"
)
_INJECTION_RE = re.compile(
    r"drop\s+all|ignore\s+(?:all\s+|previous\s+|the\s+)*instructions?"
    r"|system\s*prompt|jailbreak|без\s+ограничени|отключ\w*\s+(?:ограничени|правил|фильтр)"
    r"|забудь\s+(?:все\s+)?(?:правил|инструкц|ограничени)"
    r"|игнорир\w*\s+(?:все\s+)?(?:правил|инструкц|ограничени)"
    r"|раскрой\w*\s+(?:системн\w*\s+)?(?:промпт|инструкц)"
    r"|покажи\w*\s+(?:мне\s+)?(?:системн\w*\s+)?промпт"
    r"|(?:какой|какая|расскажи).{0,20}(?:промпт|системн\w*\s+инструкц)"
    r"|сколько\s+промпт|сколько\s+инструкций\s+в\s+систем"
    r"|расскажи.{0,20}архитектур|как\s+(?:ты\s+)?устроен\w*\s+(?:внутри|изнутри)"
    r"|kb\s+chunks|про\s+rag\b|retrieval\s+(?:систем|архитектур)"
    r"|притворись\s+(?:другим|обычным)|веди\s+себя\s+как\s+обычный\s+чат.?бот",
    re.IGNORECASE,
)

# Address / location questions ("где находится", "адрес какой", "куда ехать",
# "в каком городе"). Deliberately does NOT match "куда я записан" (that is an
# appointment-detail question handled separately).
_ADDRESS_RE = re.compile(
    r"\bадрес\b|адрес\s+клиник"
    r"|где\s+(?:вы\s+|ваша\s+|вас\s+)?(?:наход|клиник|располож)"
    r"|\bвы\s+где\b"
    r"|как\s+(?:к\s+вам\s+)?(?:про)?ехать|как\s+вас\s+найти|как\s+(?:к\s+вам\s+)?добра"
    r"|куда\s+(?:мне\s+)?(?:при)?ехать|куда\s+приезжать|куда\s+подъезж|куда\s+подход"
    r"|\bлокаци|в\s+каком\s+городе|это\s+в\s+(?:алмат|астан)|город\s+какой",
    re.IGNORECASE,
)

# "Am I booked / when / where am I booked?" — allowed to re-state details.
_APPT_DETAILS_RE = re.compile(
    r"на\s+когда\s+(?:я\s+)?запис|когда\s+(?:у\s+меня\s+)?(?:при[её]м|запис)"
    r"|во\s+сколько\s+(?:у\s+меня\s+)?(?:при[её]м|запис)"
    r"|точно\s+(?:ли\s+)?(?:меня\s+)?запис|(?:я\s+)?(?:точно\s+)?записал\w*\s*\??$"
    r"|куда\s+я\s+запис|напомн\w+\s+(?:о\s+)?(?:запис|врем|при[её]м)"
    r"|подтверд\w+\s+(?:мою\s+)?запис|детали\s+(?:моей\s+)?запис|мо[яю]\s+запис",
    re.IGNORECASE,
)

# The assistant's booking confirmation, used to recover the confirmed slot and
# to know a booking already happened (so we don't keep re-confirming).
_CONFIRM_MARKER = "записали вас на"
_LAST_CONFIRM_RE = re.compile(
    r"записали вас на\s+(послезавтра|завтра|сегодня)\s+(\d{1,2}:\d{2})",
    re.IGNORECASE,
)

# Per-stage LLM timeouts (same budget rationale as the English School demo:
# worst case planner + writer + repair must stay inside the frontend proxy abort).
_PLANNER_TIMEOUT = 8.0
_WRITER_TIMEOUT = 12.0
_REPAIR_TIMEOUT = 8.0

# ---------------------------------------------------------------------------
# Conversation status — current moment for the summary panel, changes every turn
# ---------------------------------------------------------------------------

_INTENT_TO_CONV_STATUS: dict[str, str] = {
    "ask_price":              "intent_detected",
    "ask_all_prices":         "intent_detected",
    "ask_discount":           "intent_detected",
    "wants_booking":          "agreed_next_step",
    "contact":                "contact_requested",
    "price_objection":        "objection",
    "objection":              "objection",
    "offensive":              "off_topic",
    "ask_doctor":             "exploring",
    "ask_schedule":           "exploring",
    "ask_specialty_advice":   "doctor_selection",
    "ask_preparation":        "exploring",
    "ask_services":           "exploring",
    "symptom_description":    "doctor_selection",
    "medical_advice_request": "exploring",
    "answer_question":        "exploring",
    "correction":             "exploring",
    "smalltalk":              "exploring",
    "unknown":                "exploring",
}

_CONV_STATUS_LABELS: dict[str, str] = {
    "new_dialog":        "Новый диалог",
    "consultation":      "Консультация",
    "exploring":         "Изучает варианты",
    "doctor_selection":  "Подбор врача",
    "intent_detected":   "Проявил интерес",
    "objection":         "Возражение",
    "agreed_next_step":  "Готов к записи",
    "slots_offered":     "Предложены окна",
    "awaiting_contact":  "Ожидает контакт",
    "booking_created":   "Запись создана",
    "contact_requested": "Контакт запрошен",
    "contact_collected": "Контакт получен",
    "off_topic":         "Не по теме",
    "emergency":         "Срочная помощь",
}

# Phrases that indicate the bot asked for contact info (mirrors state patterns).
_CONTACT_REQUEST_PHRASES: tuple[str, ...] = (
    "имя и номер", "оставьте контакт", "ваш номер", "ваш контакт",
    "whatsapp или telegram", "имя и whatsapp", "имя и telegram", "оставьте имя",
    "ваш whatsapp", "whatsapp/телефон", "телефон для связи",
)

# Explicit booking intent anywhere in the user's messages — used to derive the
# richer medical lead status (appointment_requested) for the DB/panel.
_BOOKING_INTENT_RE = re.compile(
    r"запиш|записат|запис[ьи]\b|хочу\s+на\s+при[её]м|оформ(?:ите|ить)?\s+(?:запись|заявку)",
    re.IGNORECASE,
)

# The user is asking about dates/availability.
_DATE_QUESTION_RE = re.compile(
    r"на\s+как(?:ую|ой|ие)\s+(?:дат|день|врем)|когда\s+можно|как(?:ие|ой)\s+(?:есть\s+)?"
    r"(?:дат|окн|врем)|свободн\w*\s+(?:окн|врем|дат)|ближайш\w+\s+(?:окн|врем|дат)"
    r"|когда\s+(?:есть\s+)?(?:окн|свободн|врем)|окн\w*\s+есть",
    re.IGNORECASE,
)
_ANY_SLOT_MENTION_RE = re.compile(
    r"(?:послезавтра|завтра|сегодня)\s+(?:в\s+)?\d{1,2}:\d{2}|\b\d{1,2}:\d{2}\b",
    re.IGNORECASE,
)
_SUGGESTED_SLOT_MENTION_RE = re.compile(
    r"хотите\s+(?:послезавтра|завтра|сегодня)\s+(?:в\s+)?\d{1,2}:\d{2}",
    re.IGNORECASE,
)
_SLOT_REJECTION_RE = re.compile(
    r"я\s+(?:послезавтра|завтра|сегодня)\s+занят"
    r"|не\s+могу\s+(?:послезавтра|завтра|сегодня)"
    r"|это\s+время\s+не\s+подходит"
    r"|нет,\s*не\s+это\s+время"
    r"|что\s+отлично"
    r"|я\s+не\s+выбирал"
    r"|я\s+не\s+просил",
    re.IGNORECASE,
)


_EM_DASH_RE = re.compile(r"\s*[—–]\s*")


def strip_em_dash(text: str) -> str:
    """Remove the em/en dash from an LLM-written answer (writer style rule 22).

    The prompt rule alone does not hold: the writer still produced "Руслан
    Ермекович — травматолог-ортопед" live. A dash between clauses becomes a
    comma; a leading dash (a list bullet) becomes nothing. Hyphens inside words
    ("травматолог-ортопед") are untouched, since they are not dashes.
    """
    if not text:
        return text
    lines = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped[:1] in ("—", "–"):
            line = line[: len(line) - len(stripped)] + stripped[1:].lstrip()
        lines.append(_EM_DASH_RE.sub(", ", line))
    return "\n".join(lines)


def _intake_metadata(intake, planner_reviewed: bool) -> dict[str, object] | None:
    """The intake record as the caller sees it, tagged with who produced it.

    ``deterministic`` — the first pass was confident and nothing else touched it.
    ``hybrid``        — the first pass drafted it and the planner reviewed it.
    ``llm``           — the first pass could not classify the complaint at all.
    """
    if not intake.is_medical_complaint and not intake.needs_llm_review:
        return None
    if not planner_reviewed:
        source = "deterministic"
    elif intake.is_medical_complaint:
        source = "hybrid"
    else:
        source = "llm"
    return intake.with_source(source).to_metadata()


def _last_assistant(history: list[ChatHistoryMessage]) -> str:
    for msg in reversed(list(history or [])):
        if msg.role == "assistant":
            return (msg.content or "").casefold()
    return ""


def _assistant_in_slot_selection(history: list[ChatHistoryMessage]) -> bool:
    """True if the assistant's last turn offered slots or proposed a specific one."""
    low = _last_assistant(history)
    return (
        "какое время вам удобнее" in low
        or "правильно понял, хотите" in low
        # Weekday-aware offers and their schedule-bound fallbacks.
        or "какое время в этом промежутке" in low
        or "удобнее утро или ближе к обеду" in low
        or "какой из них вам удобнее" in low
    )


def _booking_confirmation_sent(history: list[ChatHistoryMessage]) -> bool:
    """True if the assistant already sent the final booking confirmation."""
    return any(
        msg.role == "assistant" and _CONFIRM_MARKER in (msg.content or "").casefold()
        for msg in (history or [])
    )


def _last_confirmed_slot(history: list[ChatHistoryMessage]) -> str:
    """The slot from the most recent confirmation, e.g. "послезавтра 12:00"."""
    slot = ""
    for msg in history or []:
        if msg.role == "assistant":
            m = _LAST_CONFIRM_RE.search(msg.content or "")
            if m:
                slot = f"{m.group(1).lower()} {m.group(2)}"
    return slot


def _appointment_details_answer(state: "ConversationState") -> str:
    """Concise re-statement of the existing appointment (only when asked)."""
    return (
        f"Вы записаны на {state.selected_slot} к {specialty_dative(state.specialty)}. "
        "С вами свяжутся для подтверждения деталей."
    )


def _resolve_address_turn(
    state: "ConversationState",
    message: str,
    history: list[ChatHistoryMessage],
) -> str | None:
    """Deterministic address/location answer (works before or after booking)."""
    if not _ADDRESS_RE.search(message):
        return None
    answer = CLINIC_ADDRESS_ANSWER
    if _booking_confirmation_sent(history) and state.selected_slot and state.specialty:
        answer += (
            f" Вы записаны на {state.selected_slot} к {specialty_dative(state.specialty)}, "
            "поэтому лучше приехать за 10 минут до приёма."
        )
    return answer


# Markers that the assistant's last turn invited booking (a CTA), so a bare
# "хорошо"/"давайте" is an agreement to book, not a dead-end "Принято.".
_BOOKING_INVITE_MARKERS = (
    "окн", "подобрать", "удобное время", "записать вас", "к записи",
    "перейти к запис", "показать ближайш",
)


def _assistant_invited_booking(history: list[ChatHistoryMessage]) -> bool:
    """True if the assistant's last turn made a booking invitation/CTA."""
    low = _last_assistant(history)
    return any(marker in low for marker in _BOOKING_INVITE_MARKERS)


def _assistant_has_active_slot(history: list[ChatHistoryMessage]) -> bool:
    """True when the last assistant turn offered, suggested or echoed a slot."""
    low = _last_assistant(history)
    if not low:
        return False
    return bool(_ANY_SLOT_MENTION_RE.search(low) or _SUGGESTED_SLOT_MENTION_RE.search(low))


def _is_slot_rejection(message: str, history: list[ChatHistoryMessage]) -> bool:
    """User rejects/corrects a previously offered or mistakenly echoed slot."""
    if not _SLOT_REJECTION_RE.search(message or ""):
        return False
    return _assistant_has_active_slot(history) or bool(_ANY_SLOT_MENTION_RE.search(message or ""))


def _slot_rejection_answer(intake) -> str:
    if intake.is_medical_complaint:
        return (
            "Извините, неправильно понял. Послезавтра не ставлю. "
            "Сначала уточню по симптомам: сколько вам лет и какая температура сейчас?"
        )
    return "Поняла, это время не подходит. Какой день или время вам удобнее?"


def _assistant_asked_for_contact(history: list[ChatHistoryMessage]) -> bool:
    """True if the assistant's last turn already asked for a phone/Telegram.

    Accepts both the current wording ("пришлите ... WhatsApp/телефон") and the
    older "оставьте ..." one, which still appears in replayed transcripts.
    """
    low = _last_assistant(history)
    if "не вижу контакт" in low:
        return True
    asked = "оставьте" in low or "пришлите" in low
    return asked and ("телефон" in low or "whatsapp" in low or "контакт" in low)


def _is_booking_turn(
    state: "ConversationState",
    planner: dict,
    message: str,
    history: list[ChatHistoryMessage],
) -> bool:
    """Whether this turn is booking mechanics the deterministic handler owns."""
    current_intake = extract_medical_intake(message)
    if current_intake.is_medical_complaint:
        explicit_booking_with_time = bool(_BOOKING_INTENT_RE.search(message)) and bool(
            _ANY_SLOT_MENTION_RE.search(message)
            or (state.specialty and resolve_slot(state.specialty, message)[0] != "none")
        )
        if not explicit_booking_with_time:
            return False
    if planner.get("current_intent") == "wants_booking":
        return True
    if _BOOKING_INTENT_RE.search(message) or _DATE_QUESTION_RE.search(message):
        return True
    if state.selected_slot:
        return True
    if state.specialty and resolve_slot(state.specialty, message)[0] != "none":
        return True
    # The user agreed to a booking invitation ("хорошо"/"давайте") — offer slots
    # instead of a dead-end acknowledgement.
    if state.specialty and is_affirmation(message) and _assistant_invited_booking(history):
        return True
    # "Давайте на вторник" is a booking turn even without a booking verb.
    if state.specialty and weekday_from_text(message) is not None:
        return True
    if _assistant_in_slot_selection(history):
        # The user is replying to a slot offer/suggestion with a choice, an
        # affirmation, or their contact.
        if planner.get("current_intent") == "contact":
            return True
        if is_affirmation(message):
            return True
        if state.specialty and resolve_slot(state.specialty, message)[0] != "none":
            return True
        # A bare time answering our own weekday offer ("09:30").
        pending = _pending_offer_weekday(history)
        if pending is not None and _requested_time(message, windows_on(state.specialty, pending)):
            return True
    return False


# The user is correcting us ("Сегодня четверг. А мне надо во вторник").
_CORRECTION_RE = re.compile(
    r"\bа\s+мне\s+надо\b|\bмне\s+нужен\b|\bмне\s+нужна\b|\bя\s+же\s+(?:сказал|говорил|писал)\b"
    r"|\bне\s+завтра\b|\bне\s+это\s+врем\w*|\bвы\s+не\s+так\s+поня\w*|\bвы\s+не\s+поня\w*"
    r"|\bне\s+то\b|\bя\s+просил\b|\bсегодня\s+\w+\b\s*[.,]",
    re.IGNORECASE,
)
# "На вторник есть окна 09:30 и 12:00." — used to recover which weekday we
# offered, so a bare "09:30" reply next turn resolves against the right day.
_WEEKDAY_OFFER_RE = re.compile(r"на\s+([а-яё]+)\s+есть\s+окн", re.IGNORECASE)
_EXPLICIT_TIME_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_BARE_HOUR_RE = re.compile(r"(?<![\d:])(\d{1,2})(?![\d:])")


def _requested_time(message: str, allowed: list[str]) -> str | None:
    """The window from ``allowed`` the user picked, by exact time or bare hour."""
    low = (message or "").lower()
    for hours, minutes in _EXPLICIT_TIME_RE.findall(low):
        candidate = f"{int(hours):02d}:{minutes}"
        if candidate in allowed:
            return candidate
    for raw in _BARE_HOUR_RE.findall(_EXPLICIT_TIME_RE.sub(" ", low)):
        hour = int(raw)
        matches = [t for t in allowed if int(t.split(":")[0]) == hour]
        if len(matches) == 1:
            return matches[0]
    return None


def _pending_offer_weekday(history: list[ChatHistoryMessage]) -> int | None:
    """The weekday our last message offered windows on, if any."""
    match = _WEEKDAY_OFFER_RE.search(_last_assistant(history))
    return weekday_from_text(match.group(1)) if match else None


def _resolve_weekday_turn(
    state: "ConversationState",
    message: str,
    history: list[ChatHistoryMessage],
) -> tuple[str, str] | None:
    """Honour a named weekday, validated against the doctor's KB schedule.

    Returns (answer, conversation_status), or None to fall through to the normal
    relative-day demo slots. Never offers a day or an hour the doctor does not
    actually work, and never invents an exact free window: when the demo has no
    windows for that day it says the administrator confirms them and quotes the
    real schedule instead.
    """
    weekday = weekday_from_text(message)
    pending = _pending_offer_weekday(history)

    # A bare time reply to our own weekday offer ("09:30").
    if weekday is None and pending is not None:
        picked = _requested_time(message, windows_on(state.specialty, pending))
        if picked:
            state.selected_slot = f"{_WEEKDAY_NOMINATIVE[pending]} {picked}"
            return None  # fall through to stage 2 (ask contact / confirm)
        return None

    if weekday is None:
        return None

    dative = specialty_dative(state.specialty)
    accusative = WEEKDAY_ACCUSATIVE[weekday]
    correcting = bool(_CORRECTION_RE.search(message))
    # A correction discards whatever wrong slot we had proposed or recorded.
    if correcting:
        state.selected_slot = ""
    prefix = f"Да, поняла, вам нужен именно {_WEEKDAY_NOMINATIVE[weekday]}.\n\n" if correcting else ""

    if not works_on(state.specialty, weekday):
        days = working_days_sentence(state.specialty)
        return (
            f"{prefix}К {dative} приём в этот день не ведётся. "
            f"Врач принимает в такие дни: {days}.\n\n"
            "Какой из них вам удобнее?",
            "slots_offered",
        )

    hours = hours_on(state.specialty, weekday)
    windows = windows_on(state.specialty, weekday)

    # An exact time named together with the weekday ("запишите во вторник в 11").
    picked = _requested_time(message, windows)
    if picked:
        state.selected_slot = f"{_WEEKDAY_NOMINATIVE[weekday]} {picked}"
        return None  # stage 2 owns the contact request / confirmation
    if hours and _named_time_outside_schedule(message, state.specialty, weekday):
        return (
            f"{prefix}В это время приём не ведётся. По графику врач принимает "
            f"{schedule_sentence(state.specialty, weekday)}.\n\n"
            "Какое время в этом промежутке вам удобно?",
            "slots_offered",
        )

    # The hour is inside the schedule but not free. Say so, instead of silently
    # listing other windows as if the user had asked for nothing in particular.
    if windows and _message_names_a_time(message):
        return (
            f"{prefix}На {accusative.split()[-1]} в это время свободного окна нет. "
            f"Есть {format_slots(windows)}.\n\n"
            "Какое время вам удобнее?",
            "slots_offered",
        )

    if windows:
        listed = format_slots(windows)
        return (
            f"{prefix}На {accusative.split()[-1]} есть окна: {listed}.\n\n"
            "Какое время вам удобнее?",
            "slots_offered",
        )

    return (
        f"{prefix}На {accusative.split()[-1]} точные свободные окна уточнит администратор. "
        f"По графику врач принимает {schedule_sentence(state.specialty, weekday)}.\n\n"
        "Удобнее утро или ближе к обеду?",
        "slots_offered",
    )


def _message_names_a_time(message: str) -> bool:
    low = (message or "").lower()
    if _EXPLICIT_TIME_RE.search(low):
        return True
    return any(0 <= int(h) <= 23 for h in _BARE_HOUR_RE.findall(_EXPLICIT_TIME_RE.sub(" ", low)))


def _named_time_outside_schedule(message: str, specialty: str, weekday: int) -> bool:
    """True when the user named an hour the doctor does not work that day."""
    low = (message or "").lower()
    times = [f"{int(h):02d}:{m}" for h, m in _EXPLICIT_TIME_RE.findall(low)]
    times += [f"{int(h):02d}:00" for h in _BARE_HOUR_RE.findall(_EXPLICIT_TIME_RE.sub(" ", low))
              if 0 <= int(h) <= 23]
    if not times:
        return False
    return not any(time_within_schedule(specialty, weekday, t) for t in times)


def _resolve_booking_turn(
    state: "ConversationState",
    planner: dict,
    message: str,
    history: list[ChatHistoryMessage],
) -> tuple[str, str] | None:
    """Deterministic appointment flow. Returns (answer, conversation_status) or None.

    Controlled and safe: slots come only from the demo availability source, and
    a booking is confirmed ONLY when specialist + slot + name + contact are all
    known. Emergencies are never handled here.
    """
    if state.urgency_flag == "emergency":
        return None

    # After the booking was confirmed, do NOT keep re-confirming. Re-state the
    # details only when explicitly asked; a brand-new slot is a reschedule;
    # everything else defers to the normal flow so follow-up questions (address,
    # price, preparation, …) get real answers instead of the confirmation again.
    if _booking_confirmation_sent(history):
        if _APPT_DETAILS_RE.search(message) and state.selected_slot and state.specialty:
            return (_appointment_details_answer(state), "booking_created")
        rescheduling = (
            resolve_slot(state.specialty, message)[0] == "matched"
            and state.selected_slot
            and state.selected_slot != _last_confirmed_slot(history)
        )
        if not rescheduling:
            return None  # defer to the LLM for a genuinely new question

    if not _is_booking_turn(state, planner, message, history):
        return None
    if not state.specialty:
        return None  # let the LLM route/ask specialty (with a CTA)

    dative = specialty_dative(state.specialty)

    # ---- WEEKDAY REQUEST / CORRECTION (schedule-aware, before the demo slots) ----
    # "Давайте на вторник" names a day, so the generic "ближайшие окна" list is
    # the wrong answer: it ignores what the user asked for and can even name a
    # day the doctor does not work. Everything offered here comes from the KB
    # schedule, so a window outside the doctor's hours cannot be produced.
    weekday_turn = _resolve_weekday_turn(state, message, history)
    if weekday_turn is not None:
        return weekday_turn

    # Stage 1 — no slot chosen yet.
    if not state.selected_slot:
        kind, slot = resolve_slot(state.specialty, message)
        if kind == "suggest" and slot:
            # One plausible guess but ambiguous — confirm instead of guessing.
            return (f"Правильно понял, хотите {slot}?", "slots_offered")
        if _assistant_in_slot_selection(history):
            # Already offered — the reply didn't map. Clarify ONCE, don't re-list.
            return (
                "Не совсем понял выбор времени. Напишите, пожалуйста, день и час "
                "из предложенных, например «завтра 16:00».",
                "slots_offered",
            )
        return (
            f"К {dative} есть ближайшие окна: {format_slots(slots_for(state.specialty))}.\n\n"
            "Какое время вам удобнее?",
            "slots_offered",
        )

    # Stage 2 — slot chosen: confirm only when name AND contact are present.
    name = state.patient_name or state.contact_name
    if state.contact and name:
        return (
            f"Готово, {name}! Записали вас на {state.selected_slot} к {dative}. "
            "Администратор свяжется с вами для подтверждения деталей.",
            "booking_created",
        )

    already_asked = _assistant_asked_for_contact(history)
    slot_picked_now = resolve_slot(state.specialty, message)[0] == "matched"

    if not state.contact:
        # Acknowledge a (re)chosen slot and (re)ask for the missing fields —
        # a slot change must never be mistaken for a failed contact. The harsh
        # "Не вижу контакт" is only for a reply that was meant as the contact.
        if slot_picked_now or not already_asked:
            # Clinic-style intake wording. Age is accepted in place of a date of
            # birth (the schema stores age), so we ask for either rather than
            # rejecting what the patient naturally types.
            ask_fields: list[str] = []
            if not name:
                ask_fields.append("ФИО")
            if not state.is_known("age"):
                ask_fields.append("дату рождения или возраст")
            ask_fields.append("WhatsApp/телефон")
            if len(ask_fields) > 1:
                listed = ", ".join(ask_fields[:-1]) + " и " + ask_fields[-1]
            else:
                listed = ask_fields[0]
            lead = "Хорошо, выбрали" if already_asked else "Отлично,"
            tail = "Для завершения записи пришлите" if already_asked else "Для записи пришлите"
            return (
                f"{lead} {state.selected_slot} к {dative}.\n\n"
                f"{tail}, пожалуйста: {listed}.",
                "awaiting_contact",
            )
        return (INVALID_CONTACT_ANSWER, "awaiting_contact")

    # Contact is on file but we still need a name to finalize.
    return (
        "Спасибо! Подскажите, пожалуйста, как вас зовут — и завершу запись.",
        "awaiting_contact",
    )


def _derive_lead_status(
    state: "ConversationState",
    history: list[ChatHistoryMessage],
) -> str:
    """Monotonically increasing lead status based on full history."""
    if state.contact:
        return "contact_collected"
    for msg in history:
        if msg.role == "assistant":
            low = (msg.content or "").casefold()
            if any(p in low for p in _CONTACT_REQUEST_PHRASES):
                return "contact_requested"
    if state.contact_asked:
        return "contact_requested"
    return "open"


def _derive_medical_lead_status(
    lead_status: str,
    history: list[ChatHistoryMessage],
    message: str,
) -> str:
    """Richer medical status for the DB row and summary panel.

    Never goes on the wire ``lead_status`` (closed Literal in ChatResponse) —
    only into metadata and the Supabase ``status`` column.
    """
    if lead_status == "contact_collected":
        texts = [m.content or "" for m in history if m.role == "user"] + [message or ""]
        if any(_BOOKING_INTENT_RE.search(t) for t in texts):
            return "appointment_requested"
        return "contact_collected"
    if lead_status == "contact_requested":
        return "contact_requested"
    return "new"


def _derive_conversation_status(
    state: "ConversationState",
    history: list[ChatHistoryMessage],
    planner: dict,
    lead_status: str,
    emergency_turn: bool = False,
) -> dict[str, str]:
    """Deterministic conversation status for the summary panel."""
    if emergency_turn:
        status = "emergency"
    elif lead_status == "contact_collected":
        status = "contact_collected"
    elif lead_status == "contact_requested":
        status = "contact_requested"
    else:
        intent = planner.get("current_intent") or "unknown"
        next_step = planner.get("recommended_next_step") or ""

        if planner.get("user_frustration") and intent not in ("offensive",):
            status = "objection"
        elif next_step in ("offer_booking", "ask_contact") and intent not in (
            "objection", "price_objection", "offensive"
        ):
            status = "agreed_next_step"
        else:
            status = _INTENT_TO_CONV_STATUS.get(intent, "exploring")

        if status == "exploring" and not any(m.role == "user" for m in (history or [])):
            status = "consultation"

    return {
        "conversation_status": status,
        "conversation_status_label": _CONV_STATUS_LABELS.get(status, status),
        "conversation_status_reason": (
            f"intent={planner.get('current_intent')} "
            f"next_step={planner.get('recommended_next_step')} "
            f"urgency={state.urgency_flag} lead={lead_status}"
        ),
    }


def _safe_planner_fallback(message: str) -> dict:
    """Minimal valid plan used when the planner LLM times out."""
    return {
        "current_intent": "answer_question",
        "intent_priority": "high",
        "answers_previous_question": False,
        "user_shifted_topic": False,
        "should_pause_qualification": True,
        "user_frustration": False,
        "correction": False,
        "question_to_answer": message,
        "response_goal": "Ответь по существу на последний вопрос пользователя, опираясь на базу знаний.",
        "must_mention": [],
        "must_not_repeat": [],
        "recommended_next_step": "none",
        "do_not_ask": [],
        "handoff_recommended": False,
        "slots": {},
        "_error": "planner_timeout",
    }


async def handle_medical_center_chat(
    gemini: "GeminiService",
    payload: "ChatRequest",
) -> ChatResponse:
    history: list[ChatHistoryMessage] = list(payload.chat_history or [])
    message = payload.message or ""
    planner: dict = {}
    planner_timeout = False
    writer_timeout = False
    repair_timeout = False

    try:
        state = build_conversation_state(history, message)

        # Structured understanding of the complaint (deterministic, zero LLM).
        # Seeded into state before every short-circuit below so the summary panel
        # shows the complaint on the very first turn, whichever branch answers.
        intake = extract_conversation_intake(history, message)
        state = apply_intake_seed(state, intake)
        routing = route_symptom(message)

        # ---- EMERGENCY SHORT-CIRCUIT (deterministic, before any LLM call) ----
        # A red flag in the CURRENT message gets the fixed safe answer with no
        # booking CTA and zero LLM involvement. A follow-up message without red
        # flags resumes the normal pipeline (urgency_flag stays sticky for the
        # lead via build_conversation_state).
        red_flag = detect_red_flags(message)
        if red_flag:
            state.urgency_flag = "emergency"
            lead_status = _derive_lead_status(state, history)
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=EMERGENCY_ANSWER,
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": False,
                    "writer_llm_used": False,
                    "emergency_short_circuit": True,
                    "red_flag_category": red_flag,
                    "medical_intake": _intake_metadata(intake, planner_reviewed=False),
                    "planner_used_for_intake": False,
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    **_derive_conversation_status(
                        state, history, {}, lead_status, emergency_turn=True
                    ),
                },
            )

        # ---- PROMPT INJECTION SHORT-CIRCUIT (deterministic, before any LLM) ----
        # A probe for internal prompts/architecture/RAG or an instruction to
        # ignore the rules is deflected in code — no LLM call, so an
        # adversarial message can't talk its way past this regardless of how
        # it's phrased or which language it uses.
        if _INJECTION_RE.search(message):
            lead_status = _derive_lead_status(state, history)
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=INJECTION_REFUSAL_ANSWER,
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": False,
                    "writer_llm_used": False,
                    "injection_refusal_short_circuit": True,
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    **_derive_conversation_status(state, history, {}, lead_status),
                },
            )

        # ---- INVALID CONTACT SHORT-CIRCUIT (deterministic, before any LLM) ----
        # The user tried to leave a phone but it is implausible (wrong length).
        # Ask them to re-check instead of echoing a broken number and finalizing
        # an uncallable lead. Skipped when a valid contact is already on file.
        if not state.contact and looks_like_invalid_phone(message):
            lead_status = _derive_lead_status(state, history)
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=INVALID_CONTACT_ANSWER,
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": False,
                    "writer_llm_used": False,
                    "invalid_contact_short_circuit": True,
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    **_derive_conversation_status(state, history, {}, lead_status),
                },
            )

        # ---- SLOT REJECTION / CORRECTION SHORT-CIRCUIT ----------------------
        # If the user rejects a previously offered or mistakenly echoed slot, do
        # not let stale reconstructed state confirm it again. The demo is
        # stateless, so the "clear" happens in this response metadata and by
        # avoiding the deterministic booking path for this turn.
        if _is_slot_rejection(message, history):
            state.specialty = reconstruct_specialty_from_history(history)
            state.selected_slot = ""
            state.preferred_time = ""
            lead_status = _derive_lead_status(state, history)
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=_slot_rejection_answer(intake),
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": False,
                    "writer_llm_used": False,
                    "slot_rejection_short_circuit": True,
                    "medical_intake": _intake_metadata(intake, planner_reviewed=False),
                    "planner_used_for_intake": False,
                    "current_intent": "correction",
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    "conversation_status": "objection",
                    "conversation_status_label": _CONV_STATUS_LABELS["objection"],
                    "conversation_status_reason": "slot_rejected_by_user",
                },
            )

        # ---- ADDRESS SHORT-CIRCUIT (deterministic, before the planner) ----
        # A clinic address / location question is answered from the KB address
        # instantly — even after booking, so it never re-runs the confirmation.
        if _ADDRESS_RE.search(message):
            if not state.specialty:
                state.specialty = reconstruct_specialty_from_history(history)
            state.selected_slot = reconstruct_selected_slot(history, message, state.specialty)
            address_answer = _resolve_address_turn(state, message, history)
            if address_answer:
                lead_status = _derive_lead_status(state, history)
                booked = _booking_confirmation_sent(history)
                conv_status = "booking_created" if booked else "exploring"
                return ChatResponse(
                    route=Route.general,
                    routes=[Route.general],
                    answer=address_answer,
                    checkout=False,
                    lead_status=lead_status,
                    metadata={
                        "medical_center_demo": True,
                        "planner_llm_used": False,
                        "writer_llm_used": False,
                        "address_short_circuit": True,
                        "current_intent": "ask_services",
                        "medical_lead_status": (
                            "appointment_created" if booked
                            else _derive_medical_lead_status(lead_status, history, message)
                        ),
                        "state": state.to_metadata(),
                        "conversation_status": conv_status,
                        "conversation_status_label": _CONV_STATUS_LABELS.get(conv_status, conv_status),
                        "conversation_status_reason": f"address_short_circuit booked={booked}",
                    },
                )

        # ---- MEDICAL INTAKE SAFETY SCREEN (deterministic, before the planner) ----
        # A complaint that describes an EVENT (cut / impact / strain) always gets
        # that event's safety questions first, and a plain pain complaint that no
        # routing table covers gets the age + red-flag questions. Both are driven
        # by the complaint TYPE, never by the body part, so "порезал язык",
        # "надорвал бицепс" and "прищемил палец" work without a new patch each.
        # A complaint that DOES have a routing rule (knee, stomach, skin, …) skips
        # this and goes straight to its specialist below.
        #
        # Once the screen has been asked, we stay in it (recognised from the
        # assistant's own last message, since the server is stateless): a filler
        # reply repeats the question, a real answer routes. Genuine red flags are
        # caught by detect_red_flags above and never reach here.
        # The screen opens only on the turn that STATES the complaint (or while
        # it's already running) — never on a later "давайте" that merely accepts
        # a booking invitation, even though the complaint is still recoverable
        # from history. "Has a routing rule" is the BROAD check (route_symptom +
        # the symptom -> specialty table): "болит живот" already lands on a
        # gastroenterologist and must not be slowed down by a generic screen.
        screen_asked = assistant_asked_safety_screen(_last_assistant(history))
        current_intake = extract_medical_intake(message)
        fresh_screen_needed = needs_safety_screen(
            current_intake,
            has_routing_rule=detect_symptom_specialty(message) is not None,
        )
        if (
            (screen_asked or fresh_screen_needed)
            and not _booking_confirmation_sent(history)
            and (
                fresh_screen_needed
                or (
                    not _assistant_in_slot_selection(history)
                    and not _assistant_asked_for_contact(history)
                )
            )
        ):
            if not screen_asked or is_filler_reply(message):
                answer_text = build_safety_question(intake, age_known=state.is_known("age"))
                conv_status = "consultation"
                screen_stage = "asked" if not screen_asked else "repeated"
            else:
                specialty = specialty_for_intake(intake)
                state.specialty = specialty
                answer_text = build_routing_answer(intake, specialty_dative(specialty))
                conv_status = "doctor_selection"
                screen_stage = "routed"
            lead_status = _derive_lead_status(state, history)
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=answer_text,
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": False,
                    "writer_llm_used": False,
                    "intake_screen_short_circuit": True,
                    "intake_screen_stage": screen_stage,
                    "medical_intake": _intake_metadata(intake, planner_reviewed=False),
                    "planner_used_for_intake": False,
                    "current_intent": "symptom_description",
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    "conversation_status": conv_status,
                    "conversation_status_label": _CONV_STATUS_LABELS.get(conv_status, conv_status),
                    "conversation_status_reason": f"intake_screen={screen_stage} type={intake.complaint_type}",
                },
            )

        # ---- SYMPTOM ROUTING SHORT-CIRCUIT (deterministic, before the planner) ----
        # Obvious musculoskeletal / nerve complaints route to the right starting
        # specialist warmly and consistently (knee -> травматолог-ортопед), no
        # LLM guessing. Only on a fresh symptom turn — never mid-booking, and
        # never when the intake first pass RECOGNISED the complaint but flagged
        # it as ambiguous (e.g. neuro signs after exertion, where this table
        # would confidently pick one of two equally plausible specialists).
        # A complaint the first pass could not classify at all ("пятно на коже")
        # is not blocked: this table may well have a rule the extractor lacks.
        ambiguous_recognized = current_intake.is_medical_complaint and current_intake.needs_llm_review
        if (
            routing is not None
            and not ambiguous_recognized
            and not _booking_confirmation_sent(history)
            and not _assistant_in_slot_selection(history)
            and not _assistant_asked_for_contact(history)
        ):
            state.specialty = routing.specialty
            state.symptoms_or_goal = routing.complaint
            lead_status = _derive_lead_status(state, history)
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=f"{routing.explanation}\n\n{routing.cta}",
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": False,
                    "writer_llm_used": False,
                    "symptom_routing": routing.specialty,
                    "medical_intake": _intake_metadata(intake, planner_reviewed=False),
                    "planner_used_for_intake": False,
                    "current_intent": "symptom_description",
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    "conversation_status": "doctor_selection",
                    "conversation_status_label": _CONV_STATUS_LABELS["doctor_selection"],
                    "conversation_status_reason": f"routed to {routing.specialty}",
                },
            )

        # ---- retrieval for the planner (compact: routing/safety-relevant chunks) ----
        # State.specialty isn't populated yet this turn (that happens after the
        # planner runs) — use a read-only history lookup as a query hint only,
        # without mutating state (apply_planner_updates still owns that below).
        planner_retrieval = retrieve_medical_kb_context(
            message=message,
            history=history,
            specialty=reconstruct_specialty_from_history(history),
            symptoms_or_goal=state.symptoms_or_goal,
            mode="planner",
        )

        # ---- planner (JSON, temp 0) ----
        # Reaching here means the deterministic first pass either found nothing
        # or was not confident, so this existing planner call doubles as the
        # intake reviewer — no extra LLM call is introduced for the hybrid path.
        planner_used_for_intake = intake.needs_llm_review
        planner_call_info: dict[str, object] = {}
        try:
            planner = await asyncio.wait_for(
                plan_conversation_turn(
                    message, history, state, planner_retrieval.context, gemini,
                    call_info=planner_call_info,
                    intake_draft=intake.as_planner_draft() if intake.needs_llm_review else "",
                ),
                timeout=_PLANNER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            planner_timeout = True
            logger.warning(
                "medical_center_chat: planner timed out (message=%r)", message[:60]
            )
            planner = _safe_planner_fallback(message)

        # Deterministic safety nets — cover planner misclassification, fallback
        # and timeout alike: a "what should I take?" question must land in the
        # refusal lane, and a discount question must never trigger the
        # price-present check.
        planner = reclassify_medical_advice_question(message, planner)
        planner = reclassify_discount_question(message, planner)

        state = apply_planner_updates(state, planner)

        # Deterministic floor under the planner for the booking reply. A message
        # like "Дамир 7472438377 23" carries name + phone + age at once; when the
        # planner misses one (it did, live), we must not re-ask for something the
        # user already told us. Never overwrites what the planner did fill.
        if _assistant_asked_for_contact(history) or looks_like_contact(message):
            state = apply_booking_field_seed(state, message)

        # Stateless server: recover specialty (if the planner didn't fill it) and
        # the already-picked demo slot from the replayed history.
        if not state.specialty:
            state.specialty = reconstruct_specialty_from_history(history)
        state.selected_slot = reconstruct_selected_slot(history, message, state.specialty)
        if state.selected_slot:
            state.preferred_time = state.selected_slot  # summary shows the picked slot

        # ---- DETERMINISTIC BOOKING FLOW (controlled demo slots, no LLM) ----
        # Owns the booking mechanics so slots are never invented and a booking is
        # confirmed only when specialist + slot + name + contact are all present.
        booking = _resolve_booking_turn(state, planner, message, history)
        if booking is not None:
            answer_text, booking_status = booking
            # Reflect the real state: a contact already on file stays collected
            # even while we are still offering slots.
            lead_status = _derive_lead_status(state, history)
            if lead_status == "open" and booking_status == "awaiting_contact":
                lead_status = "contact_requested"
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=answer_text,
                checkout=False,
                lead_status=lead_status,
                metadata={
                    "medical_center_demo": True,
                    "planner_llm_used": "_error" not in planner,
                    "writer_llm_used": False,
                    "booking_stage": booking_status,
                    "current_intent": planner.get("current_intent"),
                    "medical_lead_status": (
                        "appointment_created" if booking_status == "booking_created"
                        else _derive_medical_lead_status(lead_status, history, message)
                    ),
                    "state": state.to_metadata(),
                    "conversation_status": booking_status,
                    "conversation_status_label": _CONV_STATUS_LABELS.get(
                        booking_status, booking_status
                    ),
                    "conversation_status_reason": (
                        f"booking_stage={booking_status} specialty={state.specialty} "
                        f"slot={state.selected_slot}"
                    ),
                },
            )

        # ---- retrieval for the writer (fuller: doctors/prices/FAQ/schedule) ----
        # state.specialty/symptoms_or_goal are now resolved for this turn, so
        # the writer's retrieval can be properly state-aware.
        writer_retrieval = retrieve_medical_kb_context(
            message=message,
            history=history,
            specialty=state.specialty,
            symptoms_or_goal=state.symptoms_or_goal,
            mode="writer",
        )

        # ---- writer (free-text, temp 0.35) ----
        writer_call_info: dict[str, object] = {}
        try:
            answer = await asyncio.wait_for(
                write_response(
                    message, history, state, planner, writer_retrieval.context, gemini,
                    call_info=writer_call_info,
                ),
                timeout=_WRITER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            writer_timeout = True
            logger.warning("medical_center_chat: writer timed out")
            answer = build_safe_fallback(planner, state, message)

        # Style rule 22 is enforced in code, not only in the prompt: the writer
        # still emits the em dash despite being told not to.
        answer = strip_em_dash(answer)
        validation = validate_answer(answer, state, planner)

        # ---- one repair pass if guardrail failed ----
        repaired = False
        if validation.failed:
            repaired = True
            try:
                answer = await asyncio.wait_for(
                    write_response(
                        message, history, state, planner, writer_retrieval.context, gemini,
                        repair=validation.fix, call_info=writer_call_info,
                    ),
                    timeout=_REPAIR_TIMEOUT,
                )
                answer = strip_em_dash(answer)
                validation = validate_answer(answer, state, planner)
                if validation.failed:
                    answer = build_safe_fallback(planner, state, message)
            except asyncio.TimeoutError:
                repair_timeout = True
                logger.warning("medical_center_chat: repair writer timed out")
                answer = build_safe_fallback(planner, state, message)

        # Slot guardrail (deterministic): the writer may only speak slots the
        # provider supplied — plus the already-confirmed slot. An invented
        # date/time is replaced with the safe "will check and come back" answer.
        answer, slot_guardrail_replaced = enforce_slot_guardrail(
            answer=answer,
            offered_slots=(
                slots_for(state.specialty)
                + ([state.selected_slot] if state.selected_slot else [])
            ),
            booking_context=bool(
                _BOOKING_INTENT_RE.search(message)
                or (planner or {}).get("current_intent") == "wants_booking"
            ),
        )
        if slot_guardrail_replaced:
            logger.warning(
                "medical_center_chat: slot guardrail replaced an answer with invented slots"
            )

        fallback_reason: str | None = (
            "planner_timeout" if planner_timeout
            else "writer_timeout" if writer_timeout
            else "repair_timeout" if repair_timeout
            else None
        )

        return ChatResponse(
            route=Route.general,
            routes=[Route.general],
            answer=answer.strip(),
            checkout=False,
            lead_status=(ls := _derive_lead_status(state, history)),
            metadata=_build_metadata(
                state, planner, validation, repaired,
                history=history,
                message=message,
                lead_status=ls,
                planner_timeout=planner_timeout,
                writer_timeout=writer_timeout,
                repair_timeout=repair_timeout,
                fallback_reason=fallback_reason,
                planner_kb_retrieval=planner_retrieval.to_debug_metadata(),
                kb_retrieval=writer_retrieval.to_debug_metadata(),
                planner_model_info=planner_call_info or None,
                writer_model_info=writer_call_info or None,
                medical_intake=_intake_metadata(intake, planner_used_for_intake),
                planner_used_for_intake=planner_used_for_intake,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - a demo turn must never 500
        logger.exception("medical_center_chat failed: %s", exc)
        return ChatResponse(
            route=Route.general,
            routes=[Route.general],
            answer=build_safe_fallback(planner, message=message),
            checkout=False,
            metadata={
                "medical_center_demo": True,
                "error": str(exc),
                "planner_llm_used": bool(planner) and "_error" not in planner,
                "writer_llm_used": False,
                "planner_timeout": planner_timeout,
                "writer_timeout": writer_timeout,
                "repair_timeout": repair_timeout,
            },
        )


def _build_metadata(
    state,
    planner,
    validation,
    repaired: bool,
    history: list[ChatHistoryMessage] | None = None,
    message: str = "",
    lead_status: str = "open",
    planner_timeout: bool = False,
    writer_timeout: bool = False,
    repair_timeout: bool = False,
    fallback_reason: str | None = None,
    planner_kb_retrieval: dict[str, object] | None = None,
    kb_retrieval: dict[str, object] | None = None,
    planner_model_info: dict[str, object] | None = None,
    writer_model_info: dict[str, object] | None = None,
    medical_intake: dict[str, object] | None = None,
    planner_used_for_intake: bool = False,
) -> dict[str, object]:
    conv_status = _derive_conversation_status(state, history or [], planner, lead_status)
    return {
        "medical_center_demo": True,
        "planner_llm_used": "_error" not in planner,
        "writer_llm_used": True,
        "planner_model_info": planner_model_info,
        "writer_model_info": writer_model_info,
        "medical_intake": medical_intake,
        "planner_used_for_intake": planner_used_for_intake,
        "current_intent": planner.get("current_intent"),
        "intent_priority": planner.get("intent_priority"),
        "should_pause_qualification": planner.get("should_pause_qualification"),
        "user_frustration": planner.get("user_frustration"),
        "correction": planner.get("correction"),
        "recommended_next_step": planner.get("recommended_next_step"),
        "do_not_ask": planner.get("do_not_ask"),
        "must_mention": planner.get("must_mention"),
        "handoff_recommended": planner.get("handoff_recommended"),
        "planner_reason": planner.get("reason"),
        "planner_error": planner.get("_error"),
        "medical_lead_status": _derive_medical_lead_status(lead_status, history or [], message),
        "state": state.to_metadata(),
        "validation_result": validation.to_metadata(),
        "repaired_answer": repaired,
        "escalation_used": repaired,
        "escalation_reason": "guardrail_validation_failed" if repaired else None,
        "planner_timeout": planner_timeout,
        "writer_timeout": writer_timeout,
        "repair_timeout": repair_timeout,
        "fallback_reason": fallback_reason,
        "planner_kb_retrieval": planner_kb_retrieval,
        "kb_retrieval": kb_retrieval,
        **conv_status,
    }
