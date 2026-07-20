"""Deterministic guardrails for the English School demo.

Code protects the business process. After the writer produces an answer we run
lightweight, deterministic checks. On failure the orchestrator does ONE repair
generation; if it still fails it uses an intent-aware safe fallback.

Checks:
1. No invented prices (monetary-only, normalized) — a money amount near ₸/тенге/KZT
   that is not in the KB price set fails. Non-price numbers (12 занятий, 90 минут)
   are ignored.
2. No score/result guarantees.
3. No re-asking an already-known slot.
4. If the user asked a price, the answer must contain a price.
5. No vague filler phrases.
6. Compact length — non-complex intents stay under 100 words.
7. No verbose bullet list (>3 items) for non-list intents.
8. No repeated price topics when planner sets must_not_repeat.
9. No premature contact push when planner forbids it or intent is offensive.
10. No apology in offensive context.
11. No unsupported promotions/discounts not found in KB.
12. Contact request must target the adult client, never the child/grandchild.
13. No repeated greeting once the conversation is under way.
14. No invented booking confirmations / availability claims.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .english_school_kb import get_full_kb_context
from .english_school_state import ConversationState, QUESTION_TO_SLOT, detect_asked_slots

# A money amount: digits with optional spaces / non-breaking spaces / commas as
# thousands separators, immediately followed by a currency token.
_MONEY_RE = re.compile(
    r"(\d[\d\s .,]*\d|\d)\s*(?:₸|тг\b|тенге|kzt)",
    re.IGNORECASE,
)

_GUARANTEE_RE = re.compile(
    r"гаранти|100\s*%|точно сда(?:м|ст|дите|шь)|обеща(?:ю|ем)\s+(?:балл|результат|сдать)"
    r"|свободн\w+\s+англ\w+\s+за\s+(?:месяц|1[-–]?2\s*месяц|неделю)",
    re.IGNORECASE,
)

_FORBIDDEN_PHRASES = (
    "максимальная эффективность",
    "максимально эффективно",
    "мы делаем всё возможное",
    "мы делаем все возможное",
    "понимаю ваше беспокойство",
    "понимаю ваше желание разобраться",
    "оптимизировать стоимость",
    "индивидуальные занятия позволяют максимально",
    "стоимость может показаться высокой",
    "оптимальный вариант обучения",
    "наилучшее соотношение цены и качества",
    "соотношение цены и качества",
    "лучшее соотношение цены",
)

_PRICE_INTENTS = frozenset({"ask_price", "ask_all_prices", "ask_relevant_price"})

# Intents exempt from the word-count compact check (need more room by design).
# ask_general_advice: an honest educational answer (estimate + caveats + soft
# bridge) legitimately runs longer; all other checks still apply to it.
_WORDCOUNT_EXEMPT_INTENTS = frozenset({
    "ask_all_prices", "ask_comparison", "compare_options", "ask_general_advice",
})
# Only ask_all_prices is allowed a long bullet list.
_LISTCOUNT_EXEMPT_INTENTS = frozenset({"ask_all_prices"})
_WORD_LIMIT = 100
_LIST_LINE_RE = re.compile(r"(?m)^[ \t]*(?:[-•*]|\d+\.)\s+\S")
# Price amounts that belong to each no-repeat topic.
_REPEAT_TOPIC_PRICES: dict[str, frozenset[int]] = {
    "individual_price": frozenset({9500, 72000}),
    "group_prices": frozenset({39000, 42000, 45000, 58000}),
}

_APOLOGY_RE = re.compile(r"извин|прошу прощен", re.IGNORECASE)

# Contact must belong to the adult client — never the child/grandchild.
_CHILD_CONTACT_RE = re.compile(
    r"\b(?:его|её|ее)\s+(?:имя\s+и\s+)?(?:номер|телефон|контакт)"
    r"|(?:номер|телефон|контакт)\w*\s+(?:ребёнка|ребенка|внука|внучки|сына|дочери|дочки)",
    re.IGNORECASE,
)

# Greeting at the start of an answer mid-conversation (context-reset feel).
_GREETING_RE = re.compile(
    r"^\W*(?:здравствуйте|привет|добрый\s+(?:день|вечер)|доброе\s+утро)",
    re.IGNORECASE,
)

# Claims of a confirmed booking / free slot — only the administrator confirms
# actual availability, the bot must never assert it.
_AVAILABILITY_CLAIM_RE = re.compile(
    r"записал[аи]?\s+вас|вы\s+записан[ыа]?\b|есть\s+свободн\w*\s+(?:мест|слот|окн|врем)"
    r"|есть\s+мест[оа]\b|жд[её]м\s+вас\s+(?:завтра|сегодня|в\s+\d)",
    re.IGNORECASE,
)

# Promotional terms never in KB (except the explicit 10% family discount).
_UNSUPPORTED_PROMO_RE = re.compile(
    r"рассрочк|специальн\w+\s+цен|бонус\b",
    re.IGNORECASE,
)
# Detects "скидка N%" or "N% скидка" to extract the percentage.
_DISCOUNT_PCT_RE = re.compile(r"скидк\w*\s+(\d+)\s*%|(\d+)\s*%\s*скидк", re.IGNORECASE)
# Only 10% (семейная скидка) is explicitly documented in the KB.
_KB_DISCOUNT_PCTS: frozenset[str] = frozenset({"10"})

_KB_PRICE_SET: frozenset[int] | None = None


def _normalize_amount(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _extract_money(text: str) -> set[int]:
    amounts: set[int] = set()
    for match in _MONEY_RE.finditer(text or ""):
        value = _normalize_amount(match.group(1))
        if value is not None:
            amounts.add(value)
    return amounts


def kb_price_set() -> frozenset[int]:
    """Normalized set of every money amount mentioned in the KB (cached)."""
    global _KB_PRICE_SET
    if _KB_PRICE_SET is None:
        _KB_PRICE_SET = frozenset(_extract_money(get_full_kb_context()))
    return _KB_PRICE_SET


@dataclass
class ValidationResult:
    failed: bool
    fix: str
    checks: dict[str, bool]

    def to_metadata(self) -> dict[str, object]:
        return {"failed": self.failed, "fix": self.fix, "checks": self.checks}


def validate_answer(
    answer: str,
    state: ConversationState,
    planner: dict,
    price_set: frozenset[int] | None = None,
) -> ValidationResult:
    prices = price_set if price_set is not None else kb_price_set()
    low = (answer or "").casefold()
    checks: dict[str, bool] = {}
    fixes: list[str] = []

    # 1. No invented prices (monetary-only).
    answer_money = _extract_money(answer)
    invented = {amt for amt in answer_money if amt not in prices}
    checks["no_invented_prices"] = not invented
    if invented:
        listed = ", ".join(f"{a:,}".replace(",", " ") for a in sorted(invented))
        fixes.append(
            f"Убери цены, которых нет в базе знаний ({listed} ₸). Называй только реальные цены из базы."
        )

    # 2. No guarantees.
    checks["no_guarantees"] = not bool(_GUARANTEE_RE.search(answer or ""))
    if not checks["no_guarantees"]:
        fixes.append(
            "Убери любые гарантии по баллу/результату. Объясни, что итог зависит от уровня, цели и "
            "регулярности, и предложи диагностику."
        )

    # 3. No re-asking a known slot.
    asked = detect_asked_slots(answer)
    repeated = sorted(
        q for q in asked
        if q in QUESTION_TO_SLOT and state.is_known(QUESTION_TO_SLOT[q])
    )
    checks["no_repeated_known_slot"] = not repeated
    if repeated:
        fixes.append(
            "Не переспрашивай уже известное: " + ", ".join(repeated) + ". Эти данные уже есть."
        )

    # 4. Price asked -> price present.
    intent = planner.get("current_intent")
    if intent in _PRICE_INTENTS:
        checks["price_present_when_asked"] = bool(answer_money)
        if not answer_money:
            fixes.append("Пользователь спросил цену — назови конкретную сумму из базы знаний.")

    # 5. No vague filler.
    filler = [p for p in _FORBIDDEN_PHRASES if p in low]
    checks["no_filler"] = not filler
    if filler:
        fixes.append("Убери шаблонные фразы и говори конкретикой.")

    # 6. Compact length — non-complex intents must stay under _WORD_LIMIT words.
    word_count = len((answer or "").split())
    if intent not in _WORDCOUNT_EXEMPT_INTENTS:
        checks["compact_length_ok"] = word_count <= _WORD_LIMIT
        if not checks["compact_length_ok"]:
            fixes.append(
                f"Ответ слишком длинный ({word_count} слов). "
                "Перепиши короче: 2–4 предложения, без повторов и лишних деталей."
            )
    else:
        checks["compact_length_ok"] = True

    # 7. No verbose bullet list (unless user asked for full price list).
    bullet_count = len(_LIST_LINE_RE.findall(answer or ""))
    if intent not in _LISTCOUNT_EXEMPT_INTENTS:
        checks["no_verbose_list"] = bullet_count <= 3
        if not checks["no_verbose_list"]:
            fixes.append(
                "Убери длинный маркированный список. Ответь кратко: 2–4 предложения без списков."
            )
    else:
        checks["no_verbose_list"] = True

    # 8. No repeated price topics when planner says must_not_repeat.
    must_not_repeat = planner.get("must_not_repeat") or []
    if must_not_repeat:
        repeated_price = any(
            bool(answer_money & _REPEAT_TOPIC_PRICES.get(topic, frozenset()))
            for topic in must_not_repeat
        )
        checks["no_repeated_price"] = not repeated_price
        if repeated_price:
            fixes.append(
                "Не повторяй уже упомянутые цены. "
                "Ответь на возражение без повторения цифр из предыдущих ответов."
            )

    # 9. No premature contact push when planner forbids it or intent is offensive.
    do_not_ask_list = planner.get("do_not_ask") or []
    if "contact" in do_not_ask_list or intent == "offensive":
        contact_push = "contact" in detect_asked_slots(answer)
        checks["no_premature_contact_push"] = not contact_push
        if contact_push:
            fixes.append(
                "Не запрашивай контакт — пользователь задаёт вопрос, не готов записываться. "
                "Ответь по существу без запроса WhatsApp/Telegram."
            )

    # 10. No apology in offensive context.
    if intent == "offensive":
        checks["no_apology_for_abuse"] = not bool(_APOLOGY_RE.search(answer or ""))
        if not checks["no_apology_for_abuse"]:
            fixes.append(
                "Не извиняйся. Спокойно обозначь границу и предложи вернуться к теме обучения."
            )

    # 11. No unsupported promotions (рассрочка, бонус, специальная цена, or % ≠ 10).
    promo_unsupported = bool(_UNSUPPORTED_PROMO_RE.search(answer or ""))
    pct_unsupported = any(
        (m.group(1) or m.group(2) or "") not in _KB_DISCOUNT_PCTS
        for m in _DISCOUNT_PCT_RE.finditer(answer or "")
    )
    checks["no_invented_promotion"] = not (promo_unsupported or pct_unsupported)
    if not checks["no_invented_promotion"]:
        fixes.append(
            "Не упоминай рассрочку, бонусы, специальные условия или скидки в процентах, которых нет "
            "в базе. Семейная скидка 10% на второго ребёнка — единственное, что можно упомянуть "
            "самостоятельно. По остальным условиям направь к администратору."
        )

    # 12. Contact request must target the adult client, not the child.
    child_contact = bool(_CHILD_CONTACT_RE.search(answer or ""))
    checks["no_child_contact_request"] = not child_contact
    if child_contact:
        fixes.append(
            "Не проси номер или имя ребёнка/внука. Контакт нужен у взрослого клиента: "
            "«Оставьте, пожалуйста, ваше имя и WhatsApp/Telegram для связи»."
        )

    # 13. No repeated greeting once the conversation is under way.
    if state.greeting_already_sent:
        greeted = bool(_GREETING_RE.search(answer or ""))
        checks["no_repeated_greeting"] = not greeted
        if greeted:
            fixes.append(
                "Убери приветствие («Здравствуйте», «Добрый день») — разговор уже идёт. "
                "Начни сразу с ответа по существу."
            )

    # 14. No invented booking confirmation / availability claims.
    availability = bool(_AVAILABILITY_CLAIM_RE.search(answer or ""))
    checks["no_invented_availability"] = not availability
    if availability:
        fixes.append(
            "Не подтверждай запись и не утверждай, что есть свободное время или места — "
            "наличие мест подтверждает администратор. Скажи, что администратор свяжется "
            "и предложит ближайшее доступное время."
        )

    return ValidationResult(failed=bool(fixes), fix=" ".join(fixes), checks=checks)


# ---------------------------------------------------------------------------
# Intent-aware safe fallback (never crashes, never invents facts)
# ---------------------------------------------------------------------------

_FALLBACK_PRICE_FORMAT = (
    "Чтобы не ошибиться с деталями, уточню точную информацию у администратора и вернусь с ответом. "
    "Подскажите, как с вами удобнее связаться: оставьте ваше имя и номер WhatsApp или Telegram."
)
_FALLBACK_GUARANTEE = (
    "Точный результат зависит от стартового уровня, цели и регулярности, поэтому мы начинаем с "
    "бесплатной диагностики на пробном уроке и предлагаем реалистичный план. Хотите, подберём удобное время?"
)
# Discount question — never invent a promo, never crash: state only the two
# KB-backed facts (free trial, family 10% on group format) plus the package
# economy, and offer the administrator for anything beyond that.
_FALLBACK_DISCOUNT = (
    "Не буду обещать скидку, которой нет в наших условиях. Из постоянного: пробный урок "
    "бесплатный, а при обучении двух детей из одной семьи действует скидка 10% на групповой "
    "формат. Пакет из 8 индивидуальных занятий выходит выгоднее разовых уроков. Дополнительные "
    "условия могу уточнить у администратора, напишите, если интересно."
)
# Price objection / competitor comparison — a useful commercial answer, not a
# generic deflection. No prices, no guarantees, no competitor claims.
_FALLBACK_PRICE_OBJECTION = (
    "Понимаю, разница в цене важна. Стоимость обычно зависит от длительности урока, программы, "
    "обратной связи преподавателя и плана прогресса. Если бюджет ключевой, мини-группа заметно "
    "доступнее индивидуальных занятий. На пробном уроке можно спокойно сравнить формат и "
    "преподавателя, без обязательства продолжать."
)
_FALLBACK_CONTACT = (
    "Отлично! Оставьте, пожалуйста, ваше имя и номер WhatsApp или Telegram, и администратор свяжется "
    "с вами и подберёт удобное время для пробного урока."
)
# Contact already collected — acknowledge it, never ask again, route to admin.
_FALLBACK_CONTACT_RECEIVED = (
    "Спасибо, контакт получен! Передаю заявку администратору, он свяжется с вами и предложит "
    "ближайшее доступное время для пробного урока."
)
_FALLBACK_CONTACT_RECEIVED_ASK_DETAILS = (
    _FALLBACK_CONTACT_RECEIVED
    + " Подскажите, пожалуйста, как к вам обращаться и сколько лет ученику?"
)
_FALLBACK_ADMIN_HAS_CONTACT = (
    "Детали уточню у администратора, контакт у нас уже есть, свяжемся с вами и поможем подобрать "
    "подходящий вариант."
)
_FALLBACK_GENERAL = (
    "Подскажу детали точнее с помощью администратора. Оставьте, пожалуйста, ваше имя и номер "
    "WhatsApp или Telegram, и мы свяжемся с вами и поможем."
)
_FALLBACK_OFFENSIVE = (
    "Я могу помочь с вопросами по обучению в Alem English Academy. "
    "Если захотите продолжить по программам, ценам или пробному уроку, напишите."
)
_FALLBACK_LANGUAGE = (
    "По материалам, которые у меня есть, указаны программы по английскому языку. "
    "Для уточнения других языков лучше написать администратору напрямую."
)
# General educational question — never the admin/contact push: an honest
# generic answer plus a soft diagnostic bridge.
_FALLBACK_GENERAL_ADVICE = (
    "Скорость прогресса в английском зависит от стартового уровня, регулярности занятий и "
    "практики между уроками: при 2-3 занятиях в неделю результат обычно заметен уже через "
    "несколько месяцев. Точнее сориентирует короткая бесплатная диагностика на пробном уроке."
)


def build_safe_fallback(planner: dict, state: ConversationState | None = None) -> str:
    """Intent-aware safe answer used when generation/repair fails.

    ``state`` (when available) makes the fallback contact-aware: once the user
    has left a phone/Telegram, no fallback may ask for the contact again — it
    acknowledges the contact and routes the request to the administrator.
    """
    intent = (planner or {}).get("current_intent", "unknown")
    contact_known = bool(state is not None and getattr(state, "contact", ""))

    if intent == "offensive":
        return _FALLBACK_OFFENSIVE
    if intent == "ask_language_availability":
        return _FALLBACK_LANGUAGE
    if intent == "ask_general_advice":
        return _FALLBACK_GENERAL_ADVICE
    if intent == "ask_discount":
        return _FALLBACK_DISCOUNT
    if intent in ("price_objection", "compare_competitor"):
        return _FALLBACK_PRICE_OBJECTION
    if intent in ("contact", "wants_trial"):
        if contact_known:
            ask_details = (
                state is not None
                and state.user_role == "parent"
                and not state.is_known("student_age")
            )
            return (
                _FALLBACK_CONTACT_RECEIVED_ASK_DETAILS if ask_details
                else _FALLBACK_CONTACT_RECEIVED
            )
        return _FALLBACK_CONTACT
    if intent in ("objection", "correction"):
        return _FALLBACK_GUARANTEE
    if intent in (
        "ask_price", "ask_all_prices", "ask_relevant_price",
        "ask_format", "ask_program", "ask_comparison", "compare_options",
    ):
        return _FALLBACK_ADMIN_HAS_CONTACT if contact_known else _FALLBACK_PRICE_FORMAT
    return _FALLBACK_ADMIN_HAS_CONTACT if contact_known else _FALLBACK_GENERAL
