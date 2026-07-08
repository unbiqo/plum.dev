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
from .medical_center_kb import get_full_kb_context
from .medical_center_planner import (
    plan_conversation_turn,
    reclassify_discount_question,
    reclassify_medical_advice_question,
)
from .medical_center_state import (
    ConversationState,
    apply_planner_updates,
    build_conversation_state,
    detect_red_flags,
    looks_like_invalid_phone,
)
from .medical_center_writer import write_response
from .schemas import ChatHistoryMessage, ChatResponse, Route

if TYPE_CHECKING:
    from .gemini_service import GeminiService
    from .schemas import ChatRequest

logger = logging.getLogger(__name__)

MEDICAL_CENTER_INSTANCE_ID = "damiworks_medical_center_demo"

# Deterministic reply when the user tried to leave a phone number but it is
# implausible (wrong length). Asking to re-check beats echoing a broken number
# and finalizing a lead nobody can call back. No LLM call, no lead finalized.
INVALID_CONTACT_ANSWER = (
    "Кажется, в номере телефона закралась ошибка — обычно это 11 цифр, "
    "например +7 701 234 56 78. Пришлите, пожалуйста, номер ещё раз или "
    "оставьте Telegram, и я передам заявку администратору."
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
    "ask_specialty_advice":   "exploring",
    "ask_preparation":        "exploring",
    "ask_services":           "exploring",
    "symptom_description":    "exploring",
    "medical_advice_request": "exploring",
    "answer_question":        "exploring",
    "correction":             "exploring",
    "smalltalk":              "exploring",
    "unknown":                "exploring",
}

_CONV_STATUS_LABELS: dict[str, str] = {
    "consultation":      "Консультация",
    "exploring":         "Изучает варианты",
    "intent_detected":   "Проявил интерес",
    "objection":         "Возражение",
    "agreed_next_step":  "Готов к записи",
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
        kb_context = get_full_kb_context()

        state = build_conversation_state(history, message)

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
                    "medical_lead_status": _derive_medical_lead_status(
                        lead_status, history, message
                    ),
                    "state": state.to_metadata(),
                    **_derive_conversation_status(
                        state, history, {}, lead_status, emergency_turn=True
                    ),
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

        # ---- planner (JSON, temp 0) ----
        try:
            planner = await asyncio.wait_for(
                plan_conversation_turn(message, history, state, kb_context, gemini),
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

        # ---- writer (free-text, temp 0.35) ----
        try:
            answer = await asyncio.wait_for(
                write_response(message, history, state, planner, kb_context, gemini),
                timeout=_WRITER_TIMEOUT,
            )
        except asyncio.TimeoutError:
            writer_timeout = True
            logger.warning("medical_center_chat: writer timed out")
            answer = build_safe_fallback(planner, state, message)

        validation = validate_answer(answer, state, planner)

        # ---- one repair pass if guardrail failed ----
        repaired = False
        if validation.failed:
            repaired = True
            try:
                answer = await asyncio.wait_for(
                    write_response(
                        message, history, state, planner, kb_context, gemini,
                        repair=validation.fix,
                    ),
                    timeout=_REPAIR_TIMEOUT,
                )
                validation = validate_answer(answer, state, planner)
                if validation.failed:
                    answer = build_safe_fallback(planner, state, message)
            except asyncio.TimeoutError:
                repair_timeout = True
                logger.warning("medical_center_chat: repair writer timed out")
                answer = build_safe_fallback(planner, state, message)

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
) -> dict[str, object]:
    conv_status = _derive_conversation_status(state, history or [], planner, lead_status)
    return {
        "medical_center_demo": True,
        "planner_llm_used": "_error" not in planner,
        "writer_llm_used": True,
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
        "planner_timeout": planner_timeout,
        "writer_timeout": writer_timeout,
        "repair_timeout": repair_timeout,
        "fallback_reason": fallback_reason,
        **conv_status,
    }
