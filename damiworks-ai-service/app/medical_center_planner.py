"""LLM conversation planner for the Medical Center demo (MedNova Clinic).

The *understanding* layer. Given the latest user message, the recent
conversation, the known state and the KB, it returns a small JSON plan. The
writer then turns this plan into a natural answer. Emergency red flags never
reach this planner — the orchestrator short-circuits them before any LLM call.

Temperature 0, JSON schema. Always returns a valid dict; on any LLM/parse
failure it falls back to a safe "answer the current question" plan.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .medical_center_state import ConversationState
from .schemas import ChatHistoryMessage

if TYPE_CHECKING:
    from .gemini_service import GeminiService

logger = logging.getLogger(__name__)

INTENTS = (
    "ask_price",              # a specific KB service/consultation price
    "ask_all_prices",         # explicit "все цены" / full price list
    "ask_doctor",             # about a specific doctor (who, experience, language)
    "ask_schedule",           # doctor/clinic schedule, working hours
    "ask_specialty_advice",   # "к кому идти при мигрени?" — routing, allowed
    "ask_preparation",        # how to prepare for a visit / test
    "ask_services",           # what the clinic offers, directions overview
    "ask_discount",           # discounts / promos / installments
    "symptom_description",    # user describes non-emergency symptoms
    "medical_advice_request", # diagnosis / medication / lab interpretation — refusal lane
    "wants_booking",          # wants an appointment
    "contact",                # message contains/hands over a contact
    "price_objection",
    "objection",
    "correction",
    "answer_question",
    "smalltalk",
    "offensive",
    "unknown",
)

NEXT_STEPS = (
    "ask_specialty",
    "ask_age",
    "ask_symptoms",
    "ask_preferred_time",
    "ask_contact",
    "offer_booking",
    "none",
)

PLANNER_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "current_intent": {"type": "string", "enum": list(INTENTS)},
        "intent_priority": {"type": "string", "enum": ["high", "medium", "low"]},
        "answers_previous_question": {"type": "boolean"},
        "user_shifted_topic": {"type": "boolean"},
        "should_pause_qualification": {"type": "boolean"},
        "user_frustration": {"type": "boolean"},
        "correction": {"type": "boolean"},
        "question_to_answer": {"type": "string"},
        "response_goal": {"type": "string"},
        "must_mention": {"type": "array", "items": {"type": "string"}},
        "must_not_repeat": {"type": "array", "items": {"type": "string"}},
        "recommended_next_step": {"type": "string", "enum": list(NEXT_STEPS)},
        "do_not_ask": {"type": "array", "items": {"type": "string"}},
        "handoff_recommended": {"type": "boolean"},
        "reason": {"type": "string"},
        "slots": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string"},
                "contact_name": {"type": "string"},
                "contact": {"type": "string"},
                "age": {"type": "string"},
                "specialty": {"type": "string"},
                "symptoms_or_goal": {"type": "string"},
                "preferred_time": {"type": "string"},
                "urgency": {"type": "string"},
            },
        },
    },
    "required": [
        "current_intent",
        "should_pause_qualification",
        "response_goal",
        "slots",
    ],
}

_PLANNER_SYSTEM = """\
Ты — планировщик диалога для AI-администратора медицинского центра MedNova Clinic.
Твоя работа — НЕ отвечать пользователю, а понять разговор и вернуть строгий JSON-план.

Думай как лучший администратор клиники:
- Приоритет всегда у ПОСЛЕДНЕГО сообщения пользователя. Если он спрашивает цену, врача,
  расписание или возражает — это новая тема, сбор данных для записи ставится на паузу:
  should_pause_qualification = true.
- Не предлагай повторно спрашивать то, что уже известно (см. «Уже известно»).
  Всё, что известно, добавляй в do_not_ask.
- slots: верни ВСЕ слоты, которые можно понять из всего разговора. Незаполненные — "".
- slots.specialty: направление или врач, если понятно (терапевт, педиатр, кардиолог,
  эндокринолог, гастроэнтеролог, невролог, ЛОР, дерматолог, гинеколог, уролог,
  офтальмолог, УЗИ, анализы) — или фамилия врача из базы.
- slots.age — возраст ПАЦИЕНТА (может быть ребёнок). slots.patient_name — имя пациента.
  slots.contact_name — имя того, кто пишет, если пациент ребёнок/родственник.
- slots.urgency: "urgent" если пользователь просит сегодня/срочно/очень болит, иначе "".
  Настоящие экстренные состояния обрабатываются до тебя — не решай их здесь.
- Детализация current_intent:
  * ask_price = вопрос о цене конкретной услуги/консультации.
  * ask_all_prices = явная просьба показать все цены / полный прайс. Только для него
    допустим развёрнутый список.
  * ask_specialty_advice = «к кому идти при …», «какой врач нужен, если …», «как выбрать
    специалиста». Это МАРШРУТИЗАЦИЯ (разрешена), а не диагноз: предложи направление из базы.
  * symptom_description = пользователь описывает жалобы без явного вопроса. Задача — помочь
    выбрать направление (1–2 уточняющих вопроса максимум) и предложить запись. НЕ диагноз.
  * medical_advice_request = просит диагноз («что у меня?»), лекарство/лечение («что принять?»,
    «назначьте антибиотик»), расшифровку анализов, или отменить/поменять назначение врача.
    * response_goal = «объяснить, что это может оценить только врач на приёме; ничего не
      назначать; предложить подходящего специалиста и запись».
    * handoff_recommended = false, НЕ проси контакт, если пользователь не готов записываться.
  * wants_booking = «запишите», «хочу записаться», «можно на приём». Если в сообщении уже
    есть телефон/@telegram — contact.
- Запись:
  * Контакт всегда принадлежит ВЗРОСЛОМУ, который пишет (родителю/родственнику или взрослому
    пациенту) — никогда не планируй запрашивать номер ребёнка.
  * Если контакт уже известен: НЕ ставь recommended_next_step = ask_contact. Спроси только
    недостающее (имя, возраст, удобное время) — не более одного вопроса, иначе none.
  * response_goal = «подтвердить, что заявка принята: администратор свяжется и подтвердит
    ближайшее ДОСТУПНОЕ время». НЕ выдумывай дату, время и свободные окна.
  * НЕ предполагай специализацию (особенно педиатра/детского профиля) без явных оснований
    из ТЕКУЩЕГО разговора. Если пользователь согласился записаться («давайте», «хорошо»
    и т.п.), но ни жалоба, ни специальность ещё не названы — recommended_next_step =
    ask_symptoms (спроси, что беспокоит, и возраст пациента при необходимости), а НЕ
    offer_booking.
- ask_schedule: расписание врачей и режим работы есть в базе — отвечай по базе, но точное
  свободное время подтверждает администратор.
- ask_discount: в базе есть ТОЛЬКО скидка пенсионерам 10% (будни до 13:00) и семейная
  карта 5% (от 4 визитов семьи в месяц). Других скидок/промокодов/рассрочки НЕТ — не
  изобретай; остальное уточнит администратор. НЕ ставь ask_price.
- Если цены/врача/услуги нет в базе — план должен вести к честному «уточнит администратор»,
  а НЕ к выдумыванию. Для таких вопросов НЕ требуй называть цену.
- offensive: мат, оскорбления. should_pause_qualification = true, do_not_ask: [contact],
  НЕ ставь recommended_next_step = ask_contact или offer_booking.
- must_mention: полезные факты из базы словами, без выдуманных цифр.
- recommended_next_step: ОДИН следующий шаг, только если уместен. Никогда не предлагай шаг,
  который спрашивает уже известный слот.
- do_not_ask: известные слоты + неуместное сейчас. Ярлыки: specialty, age, symptoms,
  preferred_time, contact.
- response_goal: краткая цель ответа.
- handoff_recommended = true, если нужен живой администратор (страховка, документы, жалоба,
  перенос записи, вопрос вне базы).
- НЕ придумывай факты. Ты только классифицируешь и планируешь.
Верни только JSON по схеме.\
"""


# ---------------------------------------------------------------------------
# Deterministic reclassifier — diagnosis/medication/lab questions
# ---------------------------------------------------------------------------
# «Что мне принять от головной боли?» filed under ask_price / answer_question
# would either force the price-present check on an honest refusal (repair loop)
# or let the writer answer medically. Retag it so the turn lands in the refusal
# lane deterministically.

_MEDICAL_ADVICE_RE = re.compile(
    r"что\s+(?:мне\s+)?(?:принять|попить|выпить|пропить)"
    r"|какое\s+лекарство|какие\s+таблетки|какой\s+антибиотик"
    r"|назнач(?:ь|ьте|ите)\s+(?:мне\s+)?(?:лекарство|антибиотик|лечение|таблетк|препарат)"
    r"|выпиш(?:и|ите)\s+(?:мне\s+)?(?:рецепт|лекарство|антибиотик|таблетк|препарат)"
    r"|расшифру(?:й|йте)|что\s+означа(?:ет|ют)\s+(?:мой|мои|анализ|результат)"
    r"|(?:какой|что)\s+у\s+меня\s+(?:диагноз|за\s+болезнь)|поставь(?:те)?\s+диагноз"
    r"|можно\s+ли\s+(?:мне\s+)?(?:отменить|бросить|перестать\s+пить)\s+\w*(?:лекарств|таблетк|препарат)",
    re.IGNORECASE,
)
_ADVICE_RECLASS_INTENTS = frozenset({
    "ask_price", "ask_all_prices", "ask_specialty_advice", "symptom_description",
    "ask_preparation", "answer_question", "smalltalk", "unknown",
})


def reclassify_medical_advice_question(message: str, plan: dict) -> dict:
    """Deterministically retag diagnosis/medication/lab questions."""
    if plan.get("current_intent") == "medical_advice_request":
        return plan
    if plan.get("current_intent") not in _ADVICE_RECLASS_INTENTS:
        return plan
    if not _MEDICAL_ADVICE_RE.search(message or ""):
        return plan

    plan["current_intent"] = "medical_advice_request"
    plan["handoff_recommended"] = False
    if plan.get("recommended_next_step") == "ask_contact":
        plan["recommended_next_step"] = "none"
    plan["response_goal"] = (
        "Объяснить, что диагноз, лечение и расшифровку анализов даёт только врач на приёме — "
        "ничего не назначать и не интерпретировать. Предложить подходящего специалиста из базы "
        "и мягко предложить запись."
    )
    plan["reason"] = ((plan.get("reason") or "") + " | medical_advice_reclassified").strip(" |")
    return plan


# ---------------------------------------------------------------------------
# Deterministic reclassifier — discount/promo questions
# ---------------------------------------------------------------------------
# Same production lesson as the English School demo: a discount question filed
# under a price intent forces the price-present guardrail on an honest no-₸
# answer → repair loop → slow turn. Retag to ask_discount.

_DISCOUNT_MSG_RE = re.compile(r"скидк|\bакци|промокод|рассрочк", re.IGNORECASE)
_DISCOUNT_RECLASS_INTENTS = frozenset({
    "ask_price", "ask_all_prices", "price_objection",
    "answer_question", "smalltalk", "unknown",
})


def reclassify_discount_question(message: str, plan: dict) -> dict:
    """Deterministically retag discount/promo questions to ask_discount."""
    if plan.get("current_intent") == "ask_discount":
        return plan
    if plan.get("current_intent") not in _DISCOUNT_RECLASS_INTENTS:
        return plan
    if not _DISCOUNT_MSG_RE.search(message or ""):
        return plan

    plan["current_intent"] = "ask_discount"
    plan["response_goal"] = (
        "Честно ответить про скидки, называя только условия из базы (пенсионерам 10% по будням "
        "до 13:00; семейная карта 5% при 4+ визитах семьи в месяц). Других скидок не изобретать. "
        "Остальные условия уточнит администратор."
    )
    plan["reason"] = ((plan.get("reason") or "") + " | discount_reclassified").strip(" |")
    return plan


def _format_history(history: list[ChatHistoryMessage], limit: int = 10) -> str:
    recent = (history or [])[-limit:]
    return "\n".join(
        f"{'Администратор' if m.role == 'assistant' else 'Пользователь'}: {m.content}"
        for m in recent
    )


def _build_prompt(
    message: str,
    history: list[ChatHistoryMessage],
    state: ConversationState,
    kb_context: str,
) -> str:
    parts: list[str] = [kb_context]

    known = state.known_slots()
    if known:
        parts.append("Уже известно: " + "; ".join(f"{k}={v}" for k, v in known.items()))
    if state.recent_questions_asked:
        parts.append("Администратор уже спрашивал: " + ", ".join(state.recent_questions_asked))

    convo = _format_history(history)
    if convo:
        parts.append("Недавний диалог:\n" + convo)

    parts.append(f"Последнее сообщение пользователя: «{message}»")
    parts.append("Верни JSON-план по схеме.")
    return "\n\n".join(p for p in parts if p)


def _fallback_plan(message: str, error: str | None = None) -> dict:
    plan = {
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
        "reason": "planner_fallback",
        "slots": {},
    }
    if error is not None:
        plan["_error"] = error
    return plan


async def plan_conversation_turn(
    message: str,
    history: list[ChatHistoryMessage],
    state: ConversationState,
    kb_context: str,
    gemini: "GeminiService",
) -> dict:
    """Run the planner LLM. Never raises — returns a safe default plan on failure."""
    prompt = _build_prompt(message, history, state, kb_context)
    try:
        raw = await gemini._generate_text(
            model=gemini.settings.general_model,
            model_pool=gemini.settings.general_model_pool,
            prompt=prompt,
            system_instruction=_PLANNER_SYSTEM,
            temperature=0.0,
            max_output_tokens=512,
            response_mime_type="application/json",
            response_schema=PLANNER_SCHEMA,
        )
        plan = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - planner must degrade gracefully
        logger.warning("medical_center plan_conversation_turn failed: %s", exc)
        return _fallback_plan(message, error=str(exc))

    if not isinstance(plan, dict):
        return _fallback_plan(message, error="planner returned non-object")

    # Backfill required-but-omitted keys so downstream code can rely on them.
    defaults = _fallback_plan(message)
    defaults.pop("reason", None)
    for key, value in defaults.items():
        plan.setdefault(key, value)
    plan.setdefault("reason", "")
    plan.setdefault("slots", {})
    return plan
