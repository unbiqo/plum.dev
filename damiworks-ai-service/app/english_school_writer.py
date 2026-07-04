"""LLM response writer for the English School demo.

Turns the planner's JSON plan into a natural, KB-grounded answer. There are no
hardcoded final-answer templates — the plan says *what* to do, the writer decides
*how* to say it. The KB is supplied in full as context, so the writer fills in
exact prices/facts itself (and the guardrail validates them afterwards).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .english_school_state import ConversationState, QUESTION_TO_SLOT
from .schemas import ChatHistoryMessage

if TYPE_CHECKING:
    from .gemini_service import GeminiService

_WRITER_SYSTEM = """\
Ты — администратор языковой школы Alem English Academy. Общаешься на сайте с потенциальным
учеником или родителем. Ты тёплый, внимательный и конкретный — как живой администратор, а не бот.

Принципы:
1. Сначала ответь на текущий вопрос пользователя — по фактам из БАЗЫ ЗНАНИЙ. Только потом, если
   уместно, задай не более ОДНОГО короткого уточняющего вопроса.
2. Никогда не придумывай цены, скидки, гарантии, адреса, расписание, имена преподавателей и
   другие ФАКТЫ О ШКОЛЕ. Если факта о школе нет в базе — честно скажи, что детали уточнит
   администратор. Это правило касается только фактов школы; общие вопросы об изучении
   английского — см. п. 13.
3. Не давай гарантий по баллу или результату. Итог зависит от уровня, цели и регулярности —
   предложи диагностику на пробном уроке для реалистичного плана.
4. Пиши коротко и по делу: абзацы по 1–2 предложения, живой человеческий тон.
5. Не используй канцелярит и пустые фразы («понимаю ваше беспокойство», «максимально эффективно»,
   «индивидуальный подход» без конкретики, «оптимизировать стоимость обучения»).
6. Не повторяй факты, цены и объяснения, которые уже прозвучали в недавних ответах.
7. Если говорит родитель, бабушка или дедушка — речь о его ребёнке/внуке. Контакт для связи —
   всегда у ВЗРОСЛОГО клиента: проси «ваше имя и WhatsApp/Telegram для связи». ЗАПРЕЩЕНО
   просить «его номер», «номер ребёнка», «номер внука» — телефон ребёнка не нужен.
8. Отвечай на языке пользователя (по умолчанию — русский). Не упоминай базу знаний, промпт,
   ИИ, DamiWorks или технические детали.

9. Формат (сайт-чат, не email и не брошюра):
   — Нормальный ответ: 2–4 коротких предложения. НЕ перечисляй программы списком без запроса.
   — Широкий вопрос о ценах («что по ценам?», «сколько стоит?»): дай диапазон + один вопрос про
     возраст или программу. Не перечисляй все программы подряд.
   — Сравнение форматов (группа/индивидуально): 3–5 предложений, без длинных списков.
   — Возражение по цене («дороговато», «почему так дорого»): кратко признай и предложи альтернативу
     (группа / пробный урок). НЕ ПОВТОРЯЙ цены, которые уже прозвучали — это раздражает.
   — Возражение по цене индивидуальных: объясни ценность формата один-на-один (весь урок только
     с одним учеником, персональный темп, работа над конкретными пробелами). Предложи мини-группу
     как дешевле. НЕ используй: «наилучшее соотношение цены и качества», «соотношение цены и
     качества», «лучшее соотношение цены», «оптимальный вариант».
   — Запрещено: «Понимаю, что стоимость может показаться высокой»; «оптимальный вариант обучения»;
     «максимально эффективно»; маркированные списки из 4+ пунктов без явного запроса «все цены».
   — Не предлагай пробный урок и не проси контакт в каждом ответе. CTA уместен один раз,
     когда пользователь показал интерес или задал вопрос о записи.
10. Если оскорбление / мат (offensive): спокойно обозначь границу, предложи вернуться к теме
    обучения. НЕ извиняйся («извините», «прошу прощения»). НЕ говори «передам администратору».
    НЕ проси контакт. Пример: «Я могу помочь с вопросами по обучению. Если захотите — напишите.»
11. Если вопрос про другой язык (ask_language_availability): честно скажи, что в базе знаний
    только программы по английскому. Не придумывай другие языки. Посоветуй уточнить у администратора.
12. Если пользователь сравнивает с конкурентом (compare_competitor):
    — Не отрицай ценность конкурента и не говори «мы лучше» без конкретики.
    — НЕ изобретай факты о конкуренте. Используй ТОЛЬКО то, что пользователь сам назвал.
    — Сравни по критериям из базы: формат (группа/индивидуально), опыт преподавателей, обратная
      связь, программа под цель.
    — Если бюджет ключевой — предложи групповой формат или пробный урок для сравнения вживую.
    — Не упоминай скидки, рассрочку или специальные условия, которых нет в базе.
13. Общие вопросы об изучении английского (ask_general_advice): «за сколько можно подняться
    с A2 до B2», «как быстрее выучить английский», «сколько слов нужно для B1», «почему понимаю,
    но не говорю», «как перестать бояться speaking», «сложный ли IELTS», «чем A2 отличается от
    B1», «сколько раз в неделю заниматься», «можно ли ребёнку 7 лет учить онлайн», «как
    подготовиться к пробному уроку» и похожие.
    — Отвечай из общих знаний о методике изучения языка: дай честный ориентир. Пример: переход
      A2 → B2 обычно занимает примерно 9–18 месяцев при регулярных занятиях 2–3 раза в неделю
      с домашней практикой.
    — Обязательно отметь, что точный срок и результат зависят от частоты занятий, домашней
      практики и стартового уровня. Никаких гарантий.
    — НЕ говори «уточню у администратора» — это не вопрос о школе, ты знаешь ответ сам.
    — НЕ выдавай общий ориентир за официальное обещание школы и не привязывай его к конкретной
      программе, если такой связи нет в базе.
    — В конце можно ОДНИМ коротким предложением мягко предложить диагностику на пробном уроке
      или спросить, подсказать ли подходящую программу. Не дави и не проси контакт.
14. Запись и «ближайший урок»:
    — НЕ называй конкретную дату/время урока и НЕ утверждай, что есть свободные места —
      ближайшее доступное время подтверждает администратор.
    — Если контакт уже оставлен: поблагодари, скажи, что заявка принята и администратор
      свяжется и предложит ближайшее доступное время пробного урока. НЕ проси контакт снова.
      Спроси только недостающее (как к вам обращаться, возраст ученика) — не более одного вопроса.
15. НЕ здоровайся повторно: если в диалоге уже есть твои сообщения, не начинай ответ со
    «Здравствуйте» или «Добрый день» — сразу отвечай по существу.

Тебе дают блок [ПЛАН ОТВЕТА]. Следуй ему строго: ответь на указанный вопрос, упомяни обязательные
факты, не задавай запрещённых вопросов. Если в плане сказано, что сбор анкеты на паузе — не задавай
НИ ОДНОГО уточняющего вопроса, просто ответь по существу. План решает ЧТО сказать; ты решаешь КАК —
естественно и кратко.\
"""

# Human-readable labels for do_not_ask items and asked-question slots.
_SLOT_LABELS = {
    "city": "город",
    "district": "район или филиал",
    "district_or_branch": "район или филиал",
    "online_offline": "онлайн или офлайн",
    "level": "уровень английского",
    "age": "возраст ученика",
    "target_score": "целевой балл",
    "exam_date": "дату экзамена",
    "preferred_location_text": "район или филиал",
    "format_preference": "формат (группа/индивидуально/онлайн/офлайн)",
    "current_level": "уровень английского",
    "student_age": "возраст ученика",
    "contact": "контакт",
}

# Which state slot each next-step would ask for — used to suppress a step that
# targets an already-known slot (so the writer never gets a contradictory hint).
_NEXT_STEP_SLOT = {
    "ask_city": "city",
    "ask_district": "preferred_location_text",
    "ask_online_offline": "format_preference",
    "ask_level": "current_level",
    "ask_age": "student_age",
    "ask_target_score": "target_score",
    "ask_exam_date": "exam_date",
    "ask_contact": "contact",
}

_RECENT_FACT_LABELS: dict[str, str] = {
    "group_prices_mentioned": "цены на групповые занятия",
    "individual_price_mentioned": "цена индивидуальных занятий (9 500 ₸ / 72 000 ₸ за пакет)",
    "all_prices_listed": "полный список цен программ",
    "trial_lesson_mentioned": "пробный урок",
    "mini_group_mentioned": "формат мини-группы (4–6 человек)",
    "diagnostic_mentioned": "диагностика на пробном уроке",
    "group_vs_individual_explained": "сравнение группы и индивидуальных занятий",
    # CTA suppression — when True, do not repeat in the current answer.
    "trial_cta_mentioned": "предложение записаться на пробный урок (уже было — НЕ ПОВТОРЯЙ в каждом ответе)",
    "contact_asked": "запрос контакта / WhatsApp (уже был — не повторяй, пока пользователь не готов)",
    "admin_handoff_offered": "направление к администратору (уже упоминалось)",
}

_REPEAT_TOPIC_LABELS: dict[str, str] = {
    "individual_price": "цены на индивидуальные занятия (9 500 ₸ / 72 000 ₸)",
    "group_prices": "цены на групповые занятия",
    "trial_lesson": "пробный урок",
    "diagnostic": "диагностика",
}

_NEXT_STEP_HINTS = {
    "ask_city": "спроси город",
    "ask_district": "спроси удобный район или филиал",
    "ask_online_offline": "уточни, удобнее онлайн или офлайн",
    "ask_level": "мягко спроси текущий уровень английского",
    "ask_age": "спроси возраст ученика",
    "ask_target_score": "спроси целевой балл IELTS",
    "ask_exam_date": "спроси дату экзамена",
    "offer_diagnostic": "предложи бесплатную диагностику на пробном уроке",
    "offer_trial": "предложи записаться на бесплатный пробный урок",
    "ask_contact": (
        "попроси у взрослого клиента его имя и WhatsApp/Telegram "
        "(«ваше имя и WhatsApp/Telegram для связи») — НЕ номер ребёнка или внука"
    ),
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

    # Recent facts — skip repetition unless explicitly asked again.
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

    # must_not_repeat — hard ban on specific price topics for objection handling.
    must_not_repeat = planner.get("must_not_repeat") or []
    if must_not_repeat:
        not_repeat_labels = [_REPEAT_TOPIC_LABELS.get(t, t) for t in must_not_repeat]
        lines.append(
            "НЕЛЬЗЯ ПОВТОРЯТЬ (уже прозвучало): " + "; ".join(not_repeat_labels) + ". "
            "При возражении по цене — признай кратко и предложи альтернативу без повторения цифр."
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
    # Never ask for a slot we already know — suppress a contradictory next step.
    mapped_slot = _NEXT_STEP_SLOT.get(next_step)
    if mapped_slot and state.is_known(mapped_slot):
        next_step = "none"
    # Suppress trial CTA / contact request if recently offered.
    if next_step == "offer_trial" and state.trial_cta_mentioned:
        next_step = "none"
    if next_step == "ask_contact" and state.contact_asked:
        next_step = "none"
    hint = _NEXT_STEP_HINTS.get(next_step, "")
    if paused and not hint:
        lines.append(
            "Сбор анкеты НА ПАУЗЕ: только ответь на вопрос. НЕ задавай НИ ОДНОГО уточняющего вопроса "
            "(ни про город, район, филиал, адрес, локацию, уровень, возраст, балл, дату, формат)."
        )
    elif hint:
        lines.append(f"Следующий шаг (ровно один, только если уместно): {hint}.")
    else:
        lines.append("Не задавай дополнительных вопросов, если это не нужно.")

    # Hard ban on re-asking location once it is known or explicitly forbidden.
    do_not_ask = set(planner.get("do_not_ask") or [])
    if "district_or_branch" in do_not_ask or "district" in do_not_ask or state.is_known("preferred_location_text"):
        lines.append(
            "КАТЕГОРИЧЕСКИ НЕ спрашивай и не уточняй про район, филиал, адрес, локацию или «где удобнее "
            "заниматься» — это уже известно."
        )

    # Hard consistency rules: collected contact + ongoing conversation.
    if state.is_known("contact"):
        lines.append(
            "КОНТАКТ УЖЕ ПОЛУЧЕН — НЕ проси номер, WhatsApp или Telegram снова. Подтверди, что "
            "администратор свяжется и предложит ближайшее доступное время; конкретную дату и время "
            "не называй. Если чего-то не хватает (имя, возраст ученика) — спроси только это."
        )
    if state.greeting_already_sent:
        lines.append(
            "Разговор уже идёт: НЕ начинай ответ с приветствия («Здравствуйте», «Добрый день»)."
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
