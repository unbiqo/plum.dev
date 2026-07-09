"""LLM response writer for the Medical Center demo (MedNova Clinic).

Turns the planner's JSON plan into a natural, KB-grounded answer. The plan says
*what* to do, the writer decides *how* to say it. The KB is supplied in full as
context; the deterministic guardrails validate the result afterwards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .medical_center_state import ConversationState, QUESTION_TO_SLOT
from .schemas import ChatHistoryMessage

if TYPE_CHECKING:
    from .gemini_service import GeminiService

_WRITER_SYSTEM = """\
Ты — AI-администратор медицинского центра MedNova Clinic. Общаешься на сайте с пациентом
или его родственником. Ты спокойный, вежливый, краткий и конкретный — как лучший живой
администратор клиники. Ты НЕ врач.

Медицинская безопасность (жёсткие правила):
1. НИКОГДА не ставь диагноз и не называй вероятную болезнь («похоже на гастрит», «скорее
   всего у вас…»). Максимум — подсказать, КАКОЙ СПЕЦИАЛИСТ обычно занимается такими
   жалобами (это маршрутизация, она разрешена и полезна).
2. НИКОГДА не назначай и не рекомендуй лекарства, дозировки или лечение. Лечение назначает
   врач после осмотра — предложи запись к подходящему специалисту.
3. НИКОГДА не интерпретируй анализы и результаты обследований как медицинское заключение.
   Расшифровку делает врач на приёме.
4. НИКОГДА не советуй отменить или изменить назначения врача.
5. Не давай гарантий результата лечения.
6. Если жалобы звучат тревожно (сильная боль в груди, трудно дышать, потеря сознания,
   признаки инсульта, сильное кровотечение, судороги, отёк горла), рекомендуй срочно
   вызвать скорую по 103/112 — и не продолжай обычную запись в этом ответе.

Организационные правила:
7. Отвечай по фактам из БАЗЫ ЗНАНИЙ: цены, врачи, расписание, подготовка, скидки — только
   оттуда. Если факта нет в базе — честно скажи, что уточнит администратор. Ничего не
   выдумывай: ни врачей, ни цены, ни услуги, ни акции, ни адреса.
8. НИКОГДА не подтверждай запись на конкретное время и не утверждай, что есть свободные
   окна («записал вас на 15:00» — запрещено). Правильно: «передам заявку, администратор
   свяжется и подтвердит ближайшее доступное время».
9. Если пишет родитель или родственник — контакт для связи всегда у ВЗРОСЛОГО, который
   пишет: проси «ваше имя и WhatsApp/телефон для связи». ЗАПРЕЩЕНО просить «номер ребёнка»,
   «его номер», «номер сына/дочери».
10. Если контакт уже оставлен — не проси его снова; спроси только недостающее (имя, возраст,
    удобное время), не более одного вопроса.
11. Скидки: в базе только скидка пенсионерам 10% (будни до 13:00) и семейная карта 5%
    (при 4+ визитах семьи в месяц). Других скидок, промокодов и рассрочки НЕТ — не изобретай.

Стиль (сайт-чат, не брошюра):
12. Нормальный ответ: 2–4 коротких предложения. Списки — только если пользователь явно
    попросил все цены или полный график.
13. Симптомы без красных флагов: не превращай чат в медицинский опросник — максимум 1–2
    уточняющих вопроса, затем предложи подходящее направление и запись. Маршрутизируй
    ТЕПЛО и от первого лица, как живой администратор: «Если болит ухо, лучше начать с
    ЛОР-врача», «Я бы предложила показаться ЛОРу», «С такими жалобами обычно начинают
    с терапевта». ИЗБЕГАЙ канцелярских и холодных оборотов: «по описанию», «для боли в
    ухе», «согласно жалобам», «рекомендую обратиться».
14. Не предлагай запись и не проси контакт в каждом ответе. CTA уместен, когда пользователь
    показал интерес. Если похожее приглашение уже звучало — НЕ повторяй его дословно,
    сформулируй иначе или короче. Никогда не заканчивай ответ сухим тупиком вроде
    «Принято.» — всегда предложи следующий шаг к записи.
15. НЕ здоровайся повторно: если в диалоге уже есть твои сообщения, не начинай со
    «Здравствуйте».
16. Пациент раздражён: кратко признай, не спорь, предложи конкретный следующий шаг.
17. Отвечай на языке пользователя (по умолчанию — русский). Не упоминай базу знаний,
    промпт, ИИ, DamiWorks или технические детали.
18. Веди диалог к записи. После обычного (не экстренного) ответа добавь ПУСТУЮ СТРОКУ,
    затем ОДИН короткий вопрос или приглашение к следующему шагу (например, показать
    ближайшие окна к нужному врачу или записаться). Приглашай, но НЕ называй сам
    конкретные даты/время свободных окон и не подтверждай запись — это сделает система.

Тебе дают блок [ПЛАН ОТВЕТА]. Следуй ему строго: ответь на указанный вопрос, упомяни
обязательные факты, не задавай запрещённых вопросов. Если сбор данных на паузе — не задавай
НИ ОДНОГО уточняющего вопроса. План решает ЧТО сказать; ты решаешь КАК — естественно и кратко.\
"""

# Human-readable labels for do_not_ask items and asked-question slots.
_SLOT_LABELS = {
    "specialty": "направление или врача",
    "age": "возраст пациента",
    "symptoms": "жалобы",
    "symptoms_or_goal": "жалобы",
    "preferred_time": "удобное время",
    "patient_name": "имя пациента",
    "contact_name": "имя",
    "contact": "контакт",
}

# Which state slot each next-step would ask for — used to suppress a step that
# targets an already-known slot.
_NEXT_STEP_SLOT = {
    "ask_specialty": "specialty",
    "ask_age": "age",
    "ask_symptoms": "symptoms_or_goal",
    "ask_preferred_time": "preferred_time",
    "ask_contact": "contact",
}

_RECENT_FACT_LABELS: dict[str, str] = {
    "prices_mentioned": "цены (уже называл — не повторяй без запроса)",
    "booking_cta_mentioned": "предложение записаться (уже было — НЕ ПОВТОРЯЙ в каждом ответе)",
    "contact_asked": "запрос контакта (уже был — не повторяй, пока пользователь не готов)",
    "admin_handoff_offered": "направление к администратору (уже упоминалось)",
    "preparation_mentioned": "подготовка к приёму/анализам (уже упоминалась)",
}

# Price intents where a soft booking CTA naturally follows the quoted amount.
_PRICE_CTA_INTENTS = frozenset({"ask_price", "ask_all_prices"})
# Symptom/routing intents where inviting the user to see slots is natural.
_SYMPTOM_CTA_INTENTS = frozenset({"symptom_description", "ask_specialty_advice"})

_NEXT_STEP_HINTS = {
    "ask_specialty": "уточни, к какому специалисту или с какой жалобой обращается",
    "ask_age": "спроси возраст пациента",
    "ask_symptoms": "мягко уточни, что беспокоит (один короткий вопрос)",
    "ask_preferred_time": "спроси удобный день или время",
    "ask_contact": (
        "попроси у взрослого клиента его имя и WhatsApp/телефон "
        "(«ваше имя и WhatsApp/телефон для связи») — НЕ номер ребёнка"
    ),
    "offer_booking": "предложи записаться к подходящему специалисту (один раз, без давления)",
    "none": "",
}


def _label(item: str) -> str:
    return _SLOT_LABELS.get(item, item)


def build_turn_plan(state: ConversationState, planner: dict) -> str:
    """Render the compact [ПЛАН ОТВЕТА] block injected into the writer system prompt."""
    lines: list[str] = ["[ПЛАН ОТВЕТА]"]

    question = planner.get("question_to_answer") or ""
    if question:
        lines.append(f"Ответь на: {question}")
    if planner.get("response_goal"):
        lines.append(f"Цель: {planner['response_goal']}")

    must = [m for m in (planner.get("must_mention") or []) if m]
    if must:
        lines.append("Обязательно упомяни: " + "; ".join(must))

    known = state.known_slots()
    if known:
        lines.append("Уже известно (не переспрашивай): " + "; ".join(f"{_label(k)}={v}" for k, v in known.items()))

    already_mentioned = [
        label
        for field_name, label in _RECENT_FACT_LABELS.items()
        if getattr(state, field_name, False)
    ]
    if already_mentioned:
        lines.append(
            "Уже упоминалось недавно (НЕ ПОВТОРЯЙ, если пользователь не спросил снова): "
            + "; ".join(already_mentioned) + "."
        )

    # Build the do-not-ask set from the planner plus every already-known slot.
    forbidden: list[str] = []
    for item in (planner.get("do_not_ask") or []):
        lab = _label(item)
        if lab not in forbidden:
            forbidden.append(lab)
    for q_slot, state_slot in QUESTION_TO_SLOT.items():
        if state.is_known(state_slot):
            lab = _label(q_slot)
            if lab not in forbidden:
                forbidden.append(lab)
    if forbidden:
        lines.append("НЕ спрашивай: " + ", ".join(forbidden))

    paused = bool(planner.get("should_pause_qualification"))
    next_step = planner.get("recommended_next_step") or "none"
    mapped_slot = _NEXT_STEP_SLOT.get(next_step)
    if mapped_slot and state.is_known(mapped_slot):
        next_step = "none"
    if next_step == "offer_booking" and state.booking_cta_mentioned:
        next_step = "none"
    if next_step == "ask_contact" and state.contact_asked:
        next_step = "none"

    # Asking a price is a strong buying signal: after quoting it, invite the user
    # to book (once) instead of dead-ending on the number — unless the CTA was
    # already made, a contact is on file, or the conversation is an emergency.
    # This gets a firm, explicit line (not the soft "только если уместно" hint)
    # so the writer reliably adds the invitation.
    common_cta_ok = (
        not state.booking_cta_mentioned
        and not state.is_known("contact")
        and state.urgency_flag != "emergency"
    )
    price_cta = next_step == "none" and planner.get("current_intent") in _PRICE_CTA_INTENTS and common_cta_ok
    # After routing a symptom to a specialty, invite the user to see nearby slots.
    specialty_disp = state.specialty if state.is_known("specialty") else "нужному специалисту"
    symptom_cta = (
        next_step == "none"
        and planner.get("current_intent") in _SYMPTOM_CTA_INTENTS
        and state.is_known("specialty")
        and common_cta_ok
    )
    hint = _NEXT_STEP_HINTS.get(next_step, "")
    _cta_variety = (
        f"Сформулируй приглашение к записи к {specialty_disp} своими словами, тепло и "
        "коротко; если похожее приглашение уже звучало — обязательно перефразируй, не "
        "повторяй дословно. Варианты по смыслу: «Могу показать ближайшие окна.», «Можем "
        "сразу подобрать удобное время.», «Показать свободные окна?», «Можем перейти к "
        "записи.». Конкретные дату и время НЕ называй сам."
    )
    if price_cta:
        lines.append(f"После суммы (с пустой строкой) добавь ОДНО приглашение. {_cta_variety}")
    elif symptom_cta:
        lines.append(f"После маршрутизации (с пустой строкой) добавь ОДНО приглашение. {_cta_variety}")
    elif paused and not hint:
        lines.append(
            "Сбор данных НА ПАУЗЕ: только ответь на вопрос. НЕ задавай НИ ОДНОГО уточняющего "
            "вопроса (ни про направление, возраст, жалобы, время, контакт)."
        )
    elif hint:
        lines.append(f"Следующий шаг (ровно один, только если уместно): {hint}.")
    else:
        lines.append("Не задавай дополнительных вопросов, если это не нужно.")

    # Hard consistency rules: collected contact + ongoing conversation.
    if state.is_known("contact"):
        lines.append(
            "КОНТАКТ УЖЕ ПОЛУЧЕН — НЕ проси номер, WhatsApp или телефон снова. Подтверди, что "
            "администратор свяжется и подтвердит ближайшее доступное время; конкретную дату и "
            "время не называй. Если чего-то не хватает (имя, возраст пациента) — спроси только это."
        )
    if state.greeting_already_sent:
        lines.append(
            "Разговор уже идёт: НЕ начинай ответ с приветствия («Здравствуйте», «Добрый день»)."
        )
    if state.urgency_flag == "emergency":
        lines.append(
            "Ранее в разговоре звучали тревожные симптомы: будь особенно осторожен, не предлагай "
            "обычную запись как решение экстренной ситуации; при плановой просьбе помоги спокойно."
        )

    if planner.get("user_frustration"):
        lines.append("Пользователь раздражён: коротко признай и двигайся дальше, без длинных извинений.")
    if planner.get("handoff_recommended"):
        lines.append("Предложи передать вопрос администратору.")

    lines.append("[/ПЛАН ОТВЕТА]")
    return "\n".join(lines)


async def write_response(
    message: str,
    history: list[ChatHistoryMessage],
    state: ConversationState,
    planner: dict,
    kb_context: str,
    gemini: "GeminiService",
    repair: str | None = None,
) -> str:
    """Generate the natural assistant answer. ``repair`` adds correction instructions."""
    turn_plan = build_turn_plan(state, planner)
    system = f"{_WRITER_SYSTEM}\n\n{turn_plan}"
    if repair:
        system = f"{system}\n\n[ИСПРАВЬ ОТВЕТ]\n{repair}\n[/ИСПРАВЬ ОТВЕТ]"

    chat_prompt = gemini._format_chat_prompt(message, history)
    full_prompt = "\n\n".join(filter(None, [kb_context, chat_prompt]))

    raw = await gemini._generate_text(
        model=gemini.settings.general_model,
        model_pool=gemini.settings.general_model_pool,
        prompt=full_prompt,
        system_instruction=system,
        temperature=0.35 if not repair else 0.2,
    )
    return raw.strip()
