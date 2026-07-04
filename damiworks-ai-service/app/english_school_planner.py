"""LLM conversation planner for the English School demo.

This is the *understanding* layer. Given the latest user message, the recent
conversation, the known state and the KB, it returns a small JSON plan: what the
user is actually asking now, whether stale qualification should pause, which
slots are now known, what to answer, what to proactively mention, and what NOT to
ask. The writer then turns this plan into a natural answer.

Temperature 0, JSON schema. Always returns a valid dict; on any LLM/parse
failure it falls back to a safe "answer the current question" plan.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .english_school_state import ConversationState
from .schemas import ChatHistoryMessage

if TYPE_CHECKING:
    from .gemini_service import GeminiService

logger = logging.getLogger(__name__)

INTENTS = (
    "ask_price",
    "ask_all_prices",       # user explicitly asks for all prices / full price list
    "ask_relevant_price",   # broad price question without specific context
    "ask_discount",         # "есть скидки?", "а скидка на индивидуальные?"
    "ask_format",
    "ask_program",
    "ask_language_availability",  # "А французский?", "есть немецкий?"
    "ask_comparison",       # direct format/option comparison question
    "compare_options",
    "answer_question",
    "ask_general_advice",   # general language-learning question, not a school fact
    "objection",
    "price_objection",      # "дороговато", "дорого", "недешево"
    "compare_competitor",   # user mentions a competitor price or compares schools
    "correction",
    "qualify",
    "wants_trial",
    "contact",
    "smalltalk",
    "offensive",            # abusive / profanity messages
    "unknown",
)

NEXT_STEPS = (
    "ask_city",
    "ask_district",
    "ask_online_offline",
    "ask_level",
    "ask_age",
    "ask_target_score",
    "ask_exam_date",
    "offer_diagnostic",
    "offer_trial",
    "ask_contact",
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
                "program": {"type": "string"},
                "format_preference": {"type": "string"},
                "user_role": {"type": "string"},
                "student_age": {"type": "string"},
                "current_level": {"type": "string"},
                "city": {"type": "string"},
                "preferred_location_text": {"type": "string"},
                "target_score": {"type": "string"},
                "exam_date": {"type": "string"},
                "preferred_schedule": {"type": "string"},
                "contact": {"type": "string"},
                "buyer_stage": {"type": "string"},
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
Ты — планировщик диалога для AI-администратора языковой школы Alem English Academy.
Твоя работа — НЕ отвечать пользователю, а понять разговор и вернуть строгий JSON-план.

Думай как лучший живой администратор:
- Приоритет всегда у ПОСЛЕДНЕГО сообщения пользователя. Если он спрашивает цену, формат,
  сравнение или возражает — это новая тема, и сбор анкеты (город, район, уровень) ставится
  на паузу: should_pause_qualification = true.
- Не предлагай повторно спрашивать то, что уже известно (см. «Уже известно»).
  Всё, что известно, добавляй в do_not_ask.
- slots: верни ВСЕ слоты, которые можно понять из всего разговора (а не только из
  последнего сообщения). Незаполненные оставляй пустой строкой "".
- program ∈ ielts|kids|teen|high_school|adult|speaking_club|unknown.
- format_preference ∈ group|individual|online|offline|unknown.
- slots.format_preference заполняй ТОЛЬКО если пользователь ЯВНО выбрал формат для себя
  («хочу индивидуально», «нам лучше группа», «онлайн удобнее»). Упоминание чужих цен на
  индивидуальные («возле дома индивидуальные стоят 7000», «у другой школы дешевле») — это
  сравнение цен, а НЕ выбор формата: оставь format_preference = "".
- user_role ∈ parent|adult_self|student|unknown.
- correction = true, если пользователь поправляет ранее сказанное («я же сказал», «нет, я про…»).
- Детализация current_intent:
  * ask_price = пользователь спрашивает КОНКРЕТНУЮ цену программы или формата.
  * ask_relevant_price = ШИРОКИЙ вопрос о ценах без уточнения («что по ценам?», «сколько стоит?»,
    «что за цены»). Ответ: краткий диапазон + один уточняющий вопрос (возраст / программа).
  * ask_all_prices = явная просьба показать полный список («все цены», «полный прайс», «все программы»).
    Только для ask_all_prices допустим развёрнутый список всех программ.
  * ask_comparison = прямое сравнение вариантов («группа или индивидуально», «что лучше», «чем отличаются»).
  * price_objection = «дороговато», «дорого», «недешево», «слишком дорого», «дороговат».
    Установи should_pause_qualification = true.
    В must_not_repeat перечисли темы, которые УЖЕ ПРОЗВУЧАЛИ в диалоге:
      «individual_price» — если 9 500 ₸ или 72 000 ₸ уже упоминались;
      «group_prices» — если групповые цены (39 000 / 42 000 / 45 000 / 58 000 ₸) уже называли;
      «trial_lesson» — если пробный урок уже предлагался;
      «diagnostic» — если диагностика уже упоминалась.
    Для price_objection НЕ ставь ask_price или ask_all_prices.
- Ответы в чате КОМПАКТНЫЕ: НЕ перечисляй все программы при широком вопросе.
  Для ask_relevant_price — дай диапазон (от…до) и один уточняющий вопрос про возраст или программу.
- must_not_repeat: список тем, которые нельзя повторять. Используй только для price_objection.
- Индивидуальные занятия + «дорого / дорогие / почему так дорого / цена смущает»:
  * current_intent = price_objection
  * should_pause_qualification = true
  * handoff_recommended = false (не нужен живой администратор только из-за вопроса о цене)
  * do_not_ask: НЕ добавляй «contact», если пользователь не выразил готовности записываться
  * must_not_repeat: [individual_price] если 9 500 ₸ или 72 000 ₸ уже упоминались в диалоге
  * response_goal = «объяснить ценность формата один-на-один и предложить альтернативу (мини-группа)»
- «Я имею ввиду ...» / «я про ...» / «речь об ...» после цены или формата:
  * current_intent = correction
  * correction = true, should_pause_qualification = true, handoff_recommended = false
  * do_not_ask: [contact] если пользователь не сказал «запишите», «хочу попробовать» или похожего
- compare_competitor: пользователь упоминает цену или школу конкурента
  («в другой школе стоит X», «у конкурентов дешевле», «там стоит 7 000 за час»).
  * current_intent = compare_competitor
  * should_pause_qualification = true
  * handoff_recommended = false
  * response_goal = «сравнить по критериям (формат, опыт педагога, обратная связь, план) без
    изобретения фактов конкурента; если бюджет важен — предложить группу или пробный урок»
  * must_mention: факты из нашей базы, полезные для сравнения (формат, опыт, пробный урок)
  * НЕ добавляй в must_mention факты конкурента, которых нет в нашей базе
  * НЕ заполняй slots.format_preference из сравнения цен — это не выбор формата
- Запись («запишите», «хочу записать», «запишите внука», «на ближайший урок/время»):
  * current_intent = wants_trial; если в сообщении уже есть телефон или @telegram — contact.
  * slots.contact: перенеси телефон или telegram из сообщения, если он там есть.
  * Контакт всегда принадлежит ВЗРОСЛОМУ клиенту (родителю/бабушке/дедушке или взрослому
    ученику) — никогда не планируй запрашивать номер ребёнка или внука.
  * Если контакт уже известен: НЕ ставь recommended_next_step = ask_contact. Поставь ask_age,
    если возраст ученика неизвестен, иначе none.
  * response_goal = «подтвердить, что заявка принята: администратор свяжется и предложит
    ближайшее ДОСТУПНОЕ время пробного урока». НЕ выдумывай дату, время и наличие мест.
- Возраст 15 лет — пограничный: Teen English (11–15 лет) и High School Speaking (15–17 лет) оба
  могут подходить. Если цель не указана явно, включи оба варианта в must_mention и не выбирай
  одну программу молча. Ориентир из базы: «хочет говорить/кино → High School Speaking;
  нужна школа/оценки → Teen English».
- ask_general_advice: ОБЩИЙ вопрос об изучении английского, а НЕ о фактах школы. Примеры:
  сроки перехода между уровнями («за сколько можно подняться с A2 до B2»), «как быстрее выучить
  английский», «сколько слов нужно для B1», «почему я понимаю, но не могу говорить», «как
  перестать бояться speaking», «сложный ли IELTS», «чем A2 отличается от B1», «сколько раз в
  неделю лучше заниматься», «можно ли ребёнку 7 лет учить английский онлайн», «как подготовиться
  к пробному уроку».
  * «за сколько…», «как быстро…», «сколько времени…» + уровень/выучить — это вопрос о ВРЕМЕНИ,
    а НЕ о цене. НЕ ставь ask_price для таких вопросов.
  * handoff_recommended = false — живой администратор для этого не нужен.
  * should_pause_qualification = true.
  * response_goal = «дать честный общий ориентир с оговорками (частота занятий, домашняя
    практика, стартовый уровень) и мягко предложить диагностику или подходящую программу».
  * Вопросы о ФАКТАХ ШКОЛЫ (точные цены, расписание, свободные группы, адреса, преподаватели,
    скидки, длительность конкретной программы школы) — это НЕ ask_general_advice.
- ask_discount: вопрос про скидки, акции, промокоды («есть скидки?», «а скидка на индивидуальные?»,
  «какие акции?»).
  * В базе есть ТОЛЬКО: бесплатный пробный урок и семейная скидка 10% на групповой формат для
    второго ребёнка из одной семьи. Других скидок НЕТ — не изобретай.
  * Пакет из 8 индивидуальных занятий (72 000 ₸) выгоднее разовых — это пакетная цена, НЕ скидка.
  * Запрос «большой скидки» или особых условий → предложи уточнить у администратора.
  * НЕ ставь ask_price — вопрос о скидке не требует перечислять цены.
- «Плохо усваиваю в группе» / «группа мне не подходит»: current_intent = objection или ask_format.
  * response_goal = «рекомендовать индивидуальные занятия как основной вариант (формат
    один-на-один, свой темп); для бюджета — пакет из 8 занятий; мини-группу упомянуть только
    мягко, как запасной вариант»
  * НЕ предлагай мини-группу как основную рекомендацию — пользователь только что сказал,
    что группа ему не подходит.
- ask_language_availability: пользователь спрашивает про другой язык (французский, испанский,
  немецкий, китайский и т.д.).
  * response_goal = «сообщить, что в базе только английский; посоветовать уточнить у администратора»
  * handoff_recommended = true
  * НЕ придумывай программы по другим языкам
- offensive: мат, явные оскорбления.
  * should_pause_qualification = true, handoff_recommended = false
  * do_not_ask: [contact]
  * НЕ ставь recommended_next_step = offer_trial или ask_contact
- Пробный урок / CTA:
  * Не ставь recommended_next_step = offer_trial если этот CTA уже предлагался в недавних ответах
    (признак: «предложение записаться на пробный урок» уже в «Уже упоминалось недавно»).
  * Не ставь ask_contact, если контакт уже запрашивался, уже известен, или пользователь ещё
    не готов записываться.
- slots.preferred_schedule: удобное время занятий, если пользователь упомянул
  (например: «по вечерам», «после работы», «в 18:00», «по вт/чт», «утром», «по выходным»).
  Оставь пустым, если расписание не упоминалось. Не выдумывай время.
- must_mention: какие конкретные факты полезно проактивно упомянуть. Пиши факты словами, без
  выдуманных цифр. ОБЯЗАТЕЛЬНЫЕ правила:
  * Если current_intent = ask_format и пользователь спрашивает, ЕСТЬ ли индивидуальные занятия,
    а в недавнем диалоге уже обсуждались цены/стоимость — ОБЯЗАТЕЛЬНО добавь «цена индивидуальных
    занятий» (9 500 ₸ за 60 минут; пакет из 8 занятий — 72 000 ₸). Не ограничивайся только форматом.
  * Если обсуждали оба формата и спрашивают «сколько стоит?» — добавь «цена групп и индивидуальных».
- recommended_next_step: ОДИН следующий шаг после ответа, и только если он уместен. Если
  пользователь ещё решает между форматами или только что сменил тему — выбери "none".
  Никогда не предлагай шаг, который спрашивает уже известный слот.
- do_not_ask: список тем, которые нельзя спрашивать (известные слоты + неуместные сейчас).
  Используй ярлыки: city, district, online_offline, level, age, target_score, exam_date.
- response_goal: краткая цель ответа («ответить на цену IELTS и сравнить форматы»).
- handoff_recommended = true, если нужен живой администратор (точный график/счёт/возврат/жалоба).
- НЕ придумывай факты. Ты только классифицируешь и планируешь.
Верни только JSON по схеме.\
"""


# ---------------------------------------------------------------------------
# Deterministic reclassifier — safety net for general educational questions
# ---------------------------------------------------------------------------
# «За сколько поднять уровень с A2 до B2?» is a question about TIME, not price.
# If the planner (or its fallback) files such a question under a price/program/
# generic intent, the price guardrail would demand a ₸ amount and force the
# admin fallback. Retag it here so the turn stays a normal educational answer.

_GENERAL_TIME_RE = re.compile(
    r"как быстро|сколько времени|за какое время|за сколько", re.IGNORECASE
)
_GENERAL_PROGRESS_RE = re.compile(
    r"уров(?:ень|ня|не|нем)|выуч|подн[яи]|заговор|прогресс|\b[abcабс][12]\b",
    re.IGNORECASE,
)
# Money/company words that keep the question in the protected KB lane.
_COMPANY_TOPIC_RE = re.compile(
    r"сто[ия]т|стоимост|\bцен[аыеу]|прайс|тенге|₸|оплат|скидк|рассрочк",
    re.IGNORECASE,
)
_RECLASSIFIABLE_INTENTS = frozenset({
    "ask_price", "ask_relevant_price", "ask_all_prices",
    "ask_program", "answer_question", "qualify", "unknown",
})


def reclassify_general_question(message: str, plan: dict) -> dict:
    """Deterministically retag a general timeline/progress question.

    Fires only when the message clearly asks about learning speed / level
    progress and contains no money/discount vocabulary. Never touches
    company-fact intents (schedule, contact, objections, ...).
    """
    text = message or ""
    if plan.get("current_intent") == "ask_general_advice":
        plan["handoff_recommended"] = False
        return plan
    if plan.get("current_intent") not in _RECLASSIFIABLE_INTENTS:
        return plan
    if not (_GENERAL_TIME_RE.search(text) and _GENERAL_PROGRESS_RE.search(text)):
        return plan
    if _COMPANY_TOPIC_RE.search(text):
        return plan

    plan["current_intent"] = "ask_general_advice"
    plan["handoff_recommended"] = False
    if plan.get("recommended_next_step") == "ask_contact":
        plan["recommended_next_step"] = "none"
    plan["response_goal"] = (
        "Дать честный общий ориентир по срокам/методике изучения английского с оговорками "
        "(частота занятий, домашняя практика, стартовый уровень), без обещаний школы; "
        "затем мягко предложить диагностику или подходящую программу."
    )
    plan["reason"] = ((plan.get("reason") or "") + " | general_advice_reclassified").strip(" |")
    return plan


# ---------------------------------------------------------------------------
# Deterministic reclassifier — discount/promo questions
# ---------------------------------------------------------------------------
# «А скидка на индивидуальные?» filed under ask_price forces the price-present
# guardrail on an honest "no discounts" answer (no ₸ amount) → repair loop →
# slow turn → frontend proxy timeout → generic error. Retagging to ask_discount
# keeps the turn on a single fast writer pass with the promo guardrail intact.

_DISCOUNT_MSG_RE = re.compile(r"скидк|\bакци|промокод", re.IGNORECASE)
_DISCOUNT_RECLASS_INTENTS = frozenset({
    "ask_price", "ask_all_prices", "ask_relevant_price", "ask_format",
    "price_objection", "compare_options", "answer_question", "qualify", "unknown",
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
        "Честно ответить про скидки, называя только условия из базы (бесплатный пробный урок; "
        "семейная скидка 10% на групповой формат для второго ребёнка). Никаких других скидок "
        "не изобретать. Если речь про индивидуальные — отметить, что пакет из 8 занятий "
        "выгоднее разовых, и предложить уточнить дополнительные условия у администратора."
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
    if state.recent_topics_answered:
        parts.append("Уже прозвучало в ответах: " + ", ".join(state.recent_topics_answered))

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
        logger.warning("plan_conversation_turn failed: %s", exc)
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
