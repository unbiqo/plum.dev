"""English School demo agent — LLM-first conversational assistant.

Public entrypoint for ``instance_id == "damiworks_english_school_demo"``.

Pipeline (LLM understands the conversation; code protects the business process):

    build_conversation_state  (deterministic seed)
        -> plan_conversation_turn   (LLM JSON planner, temp 0)
        -> apply_planner_updates    (state merge, slot protection)
        -> write_response           (LLM writer, temp 0.35)
        -> validate_answer          (deterministic guardrail)
        -> [one repair if it failed] -> [intent-aware safe fallback if still bad]

Each LLM call is wrapped with asyncio.wait_for(_LLM_TIMEOUT). A timeout
degrades gracefully: planner → safe default plan; writer → intent-aware
safe fallback; repair → intent-aware safe fallback. Never a 500.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .english_school_guardrails import build_safe_fallback, validate_answer
from .english_school_kb import get_full_kb_context
from .english_school_planner import plan_conversation_turn
from .english_school_state import ConversationState, apply_planner_updates, build_conversation_state
from .english_school_writer import write_response
from .schemas import ChatHistoryMessage, ChatResponse, Route

if TYPE_CHECKING:
    from .gemini_service import GeminiService
    from .schemas import ChatRequest

logger = logging.getLogger(__name__)

ENGLISH_SCHOOL_INSTANCE_ID = "damiworks_english_school_demo"

# Per-call timeout in seconds. Keeps any single turn from hanging indefinitely.
_LLM_TIMEOUT = 25.0

# ---------------------------------------------------------------------------
# Conversation status — current sales moment, changes every turn
# ---------------------------------------------------------------------------

_INTENT_TO_CONV_STATUS: dict[str, str] = {
    "ask_price":              "intent_detected",
    "ask_all_prices":         "intent_detected",
    "ask_relevant_price":     "intent_detected",
    "compare_competitor":     "intent_detected",
    "compare_options":        "intent_detected",
    "ask_comparison":         "intent_detected",
    "price_objection":        "objection",
    "objection":              "objection",
    "wants_trial":            "agreed_next_step",
    "contact":                "contact_requested",
    "offensive":              "off_topic",
    "ask_format":             "exploring",
    "ask_program":            "exploring",
    "ask_language_availability": "exploring",
    "qualify":                "exploring",
    "correction":             "exploring",
    "answer_question":        "exploring",
    "smalltalk":              "exploring",
    "unknown":                "exploring",
}

_CONV_STATUS_LABELS: dict[str, str] = {
    "consultation":     "Консультация",
    "exploring":        "Изучает варианты",
    "intent_detected":  "Проявил интерес",
    "objection":        "Возражение",
    "agreed_next_step": "Готов к записи",
    "not_ready":        "Пока не готов",
    "contact_requested":"Контакт запрошен",
    "contact_collected":"Контакт получен",
    "off_topic":        "Не по теме",
}


def _derive_conversation_status(
    state: "ConversationState",
    history: list[ChatHistoryMessage],
    planner: dict,
    lead_status: str,
) -> dict[str, str]:
    """Deterministic conversation status for the summary panel.

    Separate from lead_status (monotonic). This changes every turn to reflect
    the current sales moment: what is the user doing RIGHT NOW?
    """
    # Contact lifecycle is authoritative and monotonic.
    if lead_status == "contact_collected":
        status = "contact_collected"
    elif lead_status == "contact_requested":
        status = "contact_requested"
    else:
        intent = planner.get("current_intent") or "unknown"
        next_step = planner.get("recommended_next_step") or ""

        if planner.get("user_frustration") and intent not in ("offensive",):
            status = "objection"
        elif next_step in ("offer_trial", "ask_contact") and intent not in (
            "objection", "price_objection", "offensive"
        ):
            # Bot is actively steering toward close — user is at least ready-to-consider.
            status = "agreed_next_step"
        else:
            status = _INTENT_TO_CONV_STATUS.get(intent, "exploring")

        # First message ever = still in pure consultation mode.
        if status == "exploring" and not any(
            m.role == "user" for m in (history or [])
        ):
            status = "consultation"

    return {
        "conversation_status": status,
        "conversation_status_label": _CONV_STATUS_LABELS.get(status, status),
        "conversation_status_reason": (
            f"intent={planner.get('current_intent')} "
            f"next_step={planner.get('recommended_next_step')} "
            f"frustration={planner.get('user_frustration')} "
            f"lead={lead_status}"
        ),
    }

# Phrases that indicate the bot asked for contact info (mirrors state.py patterns).
_CONTACT_REQUEST_PHRASES: tuple[str, ...] = (
    "имя и номер", "оставьте контакт", "ваш номер", "ваш контакт",
    "whatsapp или telegram", "имя и whatsapp", "имя и telegram", "оставьте имя",
)


def _derive_lead_status(
    state: "ConversationState",
    history: list[ChatHistoryMessage],
) -> str:
    """Return a monotonically increasing lead status based on full history.

    Scanning the whole history prevents status regression when CTA suppression
    causes the bot to stop repeating contact requests.
    """
    if state.contact:
        return "contact_collected"
    # Scan ALL assistant turns (not just the recent 3 that state tracks).
    for msg in history:
        if msg.role == "assistant":
            low = (msg.content or "").casefold()
            if any(p in low for p in _CONTACT_REQUEST_PHRASES):
                return "contact_requested"
    # Also check current-turn tracking (covers the turn being built right now).
    if state.contact_asked:
        return "contact_requested"
    return "open"


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


async def handle_english_school_chat(
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

        # ---- planner (JSON, temp 0) ----
        try:
            planner = await asyncio.wait_for(
                plan_conversation_turn(message, history, state, kb_context, gemini),
                timeout=_LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            planner_timeout = True
            logger.warning(
                "english_school_chat: planner timed out (message=%r)", message[:60]
            )
            planner = _safe_planner_fallback(message)

        state = apply_planner_updates(state, planner)

        # ---- writer (free-text, temp 0.35) ----
        try:
            answer = await asyncio.wait_for(
                write_response(message, history, state, planner, kb_context, gemini),
                timeout=_LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            writer_timeout = True
            logger.warning("english_school_chat: writer timed out")
            answer = build_safe_fallback(planner)

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
                    timeout=_LLM_TIMEOUT,
                )
                validation = validate_answer(answer, state, planner)
                if validation.failed:
                    answer = build_safe_fallback(planner)
            except asyncio.TimeoutError:
                repair_timeout = True
                logger.warning("english_school_chat: repair writer timed out")
                answer = build_safe_fallback(planner)

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
                lead_status=ls,
                planner_timeout=planner_timeout,
                writer_timeout=writer_timeout,
                repair_timeout=repair_timeout,
                fallback_reason=fallback_reason,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - a demo turn must never 500
        logger.exception("english_school_chat failed: %s", exc)
        return ChatResponse(
            route=Route.general,
            routes=[Route.general],
            answer=build_safe_fallback(planner),
            checkout=False,
            metadata={
                "english_school_demo": True,
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
    lead_status: str = "open",
    planner_timeout: bool = False,
    writer_timeout: bool = False,
    repair_timeout: bool = False,
    fallback_reason: str | None = None,
) -> dict[str, object]:
    conv_status = _derive_conversation_status(state, history or [], planner, lead_status)
    return {
        "english_school_demo": True,
        "planner_llm_used": "_error" not in planner,
        "writer_llm_used": True,
        "current_intent": planner.get("current_intent"),
        "intent_priority": planner.get("intent_priority"),
        "should_pause_qualification": planner.get("should_pause_qualification"),
        "user_shifted_topic": planner.get("user_shifted_topic"),
        "answers_previous_question": planner.get("answers_previous_question"),
        "user_frustration": planner.get("user_frustration"),
        "correction": planner.get("correction"),
        "recommended_next_step": planner.get("recommended_next_step"),
        "do_not_ask": planner.get("do_not_ask"),
        "must_mention": planner.get("must_mention"),
        "handoff_recommended": planner.get("handoff_recommended"),
        "planner_reason": planner.get("reason"),
        "planner_error": planner.get("_error"),
        "state": state.to_metadata(),
        "buyer_stage": state.buyer_stage,
        "validation_result": validation.to_metadata(),
        "repaired_answer": repaired,
        "planner_timeout": planner_timeout,
        "writer_timeout": writer_timeout,
        "repair_timeout": repair_timeout,
        "fallback_reason": fallback_reason,
        **conv_status,
    }
