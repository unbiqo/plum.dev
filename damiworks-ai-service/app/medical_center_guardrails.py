"""Deterministic guardrails for the Medical Center demo (MedNova Clinic).

Code protects the patient and the business process. After the writer produces
an answer we run lightweight, deterministic checks. On failure the orchestrator
does ONE repair generation; if it still fails it uses an intent-aware safe
fallback. Emergency red flags never reach the LLM at all — the orchestrator
answers them with ``EMERGENCY_ANSWER`` before the planner runs (the detector
itself lives in ``medical_center_state.detect_red_flags``).

Checks:
1.  No invented prices — money amounts near ₸/тенге must all be in the KB set.
2.  No diagnosis in the bot's answer.
3.  No medication/treatment prescription (incl. concrete drug names, dosages).
4.  No lab-result interpretation.
5.  No invented booking confirmations / free-slot claims (admin confirms slots).
6.  Contact request must target the adult client, never the child.
7.  No invented doctors (names not present in the KB doctors section).
8.  No unsupported promotions (only the KB's 10% pensioner / 5% family card).
9.  If the user asked a price, the answer contains a KB price or an honest
    admin handoff.
10. No treatment-result guarantees.
11. Compact length / no verbose bullet lists (with list-friendly intents exempt).
12. No premature contact push when the planner forbids it or intent is offensive.
13. No re-asking an already-known slot.
14. No repeated greeting mid-conversation.
15. No booking CTA while the conversation is still in an emergency context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .medical_center_kb import get_full_kb_context
from .medical_center_state import (
    ConversationState,
    QUESTION_TO_SLOT,
    detect_asked_slots,
    detect_symptom_specialty,
)

# Exact wording required for emergency turns (KB red-flag template, short form).
EMERGENCY_ANSWER = (
    "По описанию это может требовать срочной помощи. Я не могу оценить состояние "
    "дистанционно. Пожалуйста, вызовите скорую по 103/112 или обратитесь в ближайший "
    "стационар."
)

# A money amount: digits with optional thousands separators, immediately
# followed by a currency token.
_MONEY_RE = re.compile(
    r"(\d[\d\s .,]*\d|\d)\s*(?:₸|тг\b|тенге|kzt)",
    re.IGNORECASE,
)

# --- medical safety patterns (applied to the BOT's answer) -------------------

_DIAGNOSIS_RE = re.compile(
    r"у\s+вас\s+(?:скорее\s+всего|похоже|вероятно|наверняка|возможно)"
    r"|(?:скорее\s+всего|вероятно|похоже),?\s+(?:это|у\s+вас)"
    r"|похоже\s+на\s+(?:\w+ит\b|\w+оз\b|ангин|мигрен|инфаркт|инсульт|аппендицит|пневмони|грипп|орви)"
    r"|у\s+вас\s+(?!визит)\w+(?:ит|оз)\b"
    r"|ваш\s+диагноз|могу\s+предположить,?\s+что\s+у\s+вас",
    re.IGNORECASE,
)

_PRESCRIPTION_RE = re.compile(
    r"\bприми(?:те)?\b|\bпринимайте\b|\bпейте\b|\bвыпейте\b|\bпопейте\b|\bпропейте\b"
    r"|назнача\w+\s+(?:вам\s+)?(?:курс|препарат|лекарст|антибиотик)"
    r"|рекоменду\w+\s+(?:принимать|попить|пропить)"
    r"|начните\s+принимать|\b\d+\s*мг\b"
    r"|\b(?:ибупрофен|парацетамол|нурофен|аспирин|анальгин|амоксициллин|азитромицин|но-шп\w*)\b",
    re.IGNORECASE,
)

_LAB_INTERPRETATION_RE = re.compile(
    r"ваш\w*\s+(?:анализ|результат)\w*\s+(?:показыва|означа|говор|в\s+норме|выше\s+нормы|ниже\s+нормы)"
    r"|по\s+ваш\w+\s+анализ\w+\s+(?:вижу|видно|можно\s+сказать)"
    r"|расшифру[юем]\b"
    r"|(?:это|у\s+вас)\s+(?:в\s+пределах\s+нормы|выше\s+нормы|ниже\s+нормы)",
    re.IGNORECASE,
)

_GUARANTEE_RE = re.compile(
    r"гаранти|100\s*%|полностью\s+вылеч|точно\s+помо(?:жет|гут)"
    r"|обеща(?:ю|ем)\s+(?:результат|выздоров|что)",
    re.IGNORECASE,
)
# Honest guarantee DISCLAIMERS are allowed (the writer is told to answer the
# "а вы гарантируете?" question like a human: no guarantees + doctor's
# experience + offer the first visit). They are scrubbed from the answer before
# the guarantee check, so only AFFIRMATIVE guarantees still fail it.
_NEGATED_GUARANTEE_RE = re.compile(
    r"не\s+да[юё]\w*\s+(?:\w+\s+){0,2}?гарант\w+"          # «не даёт (никаких) гарантий»
    r"|не\s+(?:могу|можем|обеща\w+)\s+(?:\w+\s+){0,2}?гарант\w+"
    r"|гарант\w+(?:\s+\w+){0,3}\s+не\s+(?:да[юё]\w*|быва\w+|обеща\w+)"
    r"|не\s+гарантиру\w+"
    r"|без\s+гарантий",
    re.IGNORECASE,
)

# Claims of a confirmed booking / free slot — only the administrator confirms.
_AVAILABILITY_CLAIM_RE = re.compile(
    r"записал[аи]?\s+вас|вы\s+записан[ыа]?\b|есть\s+свободн\w*\s+(?:мест|слот|окн|врем)"
    r"|есть\s+мест[оа]\b|жд[её]м\s+вас\s+(?:завтра|сегодня|в\s+\d)"
    r"|приходите\s+(?:завтра|сегодня)?\s*(?:в|к)\s+\d{1,2}[:.]?\d{0,2}\b",
    re.IGNORECASE,
)

# Contact must belong to the adult client — never the child/patient-relative.
_CHILD_CONTACT_RE = re.compile(
    r"\b(?:его|её|ее)\s+(?:имя\s+и\s+)?(?:номер|телефон|контакт)"
    r"|(?:номер|телефон|контакт)\w*\s+(?:ребёнка|ребенка|сына|дочери|дочки|внука|внучки)",
    re.IGNORECASE,
)

# Greeting at the start of an answer mid-conversation.
_GREETING_RE = re.compile(
    r"^\W*(?:здравствуйте|привет|добрый\s+(?:день|вечер)|доброе\s+утро)",
    re.IGNORECASE,
)

# Promotional terms never in the KB (KB has only: 10% pensioners, 5% family card).
_UNSUPPORTED_PROMO_RE = re.compile(
    r"рассрочк|промокод|специальн\w+\s+цен|бонус\b",
    re.IGNORECASE,
)
_DISCOUNT_PCT_RE = re.compile(r"скидк\w*\s+(\d+)\s*%|(\d+)\s*%\s*(?:скидк|на\s+консультац)", re.IGNORECASE)
_KB_DISCOUNT_PCTS: frozenset[str] = frozenset({"10", "5"})

# Doctor-name mentions: "врач/доктор <Имя>". Every capitalized token after the
# title must exist in the KB doctors section.
_DOCTOR_MENTION_RE = re.compile(
    r"(?:врач|доктор|специалист)\w*\s+((?:[А-ЯЁ][а-яё]{2,}\s*){1,2})"
)

# Booking pushes while the conversation is in an emergency context.
_BOOKING_PUSH_RE = re.compile(r"запис|запиш|оформим\s+заявку", re.IGNORECASE)
_EMERGENCY_CONTEXT_INTENTS = frozenset({
    "symptom_description", "medical_advice_request", "answer_question", "unknown",
})

_PRICE_INTENTS = frozenset({"ask_price", "ask_all_prices"})
# Intents that legitimately need more room / a list.
_WORDCOUNT_EXEMPT_INTENTS = frozenset({"ask_all_prices", "ask_schedule", "ask_preparation"})
_LISTCOUNT_EXEMPT_INTENTS = frozenset({"ask_all_prices", "ask_schedule"})
_WORD_LIMIT = 100
_LIST_LINE_RE = re.compile(r"(?m)^[ \t]*(?:[-•*]|\d+\.)\s+\S")

_FORBIDDEN_PHRASES = (
    "понимаю ваше беспокойство",
    "максимально эффективно",
    "мы делаем всё возможное",
    "мы делаем все возможное",
)

_KB_PRICE_SET: frozenset[int] | None = None
_KB_DOCTOR_NAMES: frozenset[str] | None = None


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


def kb_doctor_names() -> frozenset[str]:
    """Every capitalized name token from the KB doctors section (cached)."""
    global _KB_DOCTOR_NAMES
    if _KB_DOCTOR_NAMES is None:
        kb = get_full_kb_context()
        names: set[str] = set()
        section = re.search(r"## Врачи и расписание(.*?)(?:\n## |\[/БАЗА)", kb, re.DOTALL)
        for match in re.finditer(r"^- ([А-ЯЁ][а-яё]+) ([А-ЯЁ][а-яё]+) —", section.group(1) if section else kb, re.MULTILINE):
            names.add(match.group(1))
            names.add(match.group(2))
        _KB_DOCTOR_NAMES = frozenset(names)
    return _KB_DOCTOR_NAMES


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
    intent = planner.get("current_intent")

    # 1. No invented prices (monetary-only).
    answer_money = _extract_money(answer)
    invented = {amt for amt in answer_money if amt not in prices}
    checks["no_invented_prices"] = not invented
    if invented:
        listed = ", ".join(f"{a:,}".replace(",", " ") for a in sorted(invented))
        fixes.append(
            f"Убери цены, которых нет в базе знаний ({listed} ₸). Называй только реальные цены из базы; "
            "если цены нет — скажи, что уточнит администратор."
        )

    # 2. No diagnosis.
    checks["no_diagnosis"] = not bool(_DIAGNOSIS_RE.search(answer or ""))
    if not checks["no_diagnosis"]:
        fixes.append(
            "Не ставь диагноз и не называй вероятную болезнь. Скажи, что оценить состояние может "
            "только врач на приёме, и предложи подходящего специалиста."
        )

    # 3. No prescription.
    checks["no_prescription"] = not bool(_PRESCRIPTION_RE.search(answer or ""))
    if not checks["no_prescription"]:
        fixes.append(
            "Не рекомендуй лекарства, дозировки или лечение. Лечение назначает врач после осмотра — "
            "предложи запись к специалисту."
        )

    # 4. No lab interpretation.
    checks["no_lab_interpretation"] = not bool(_LAB_INTERPRETATION_RE.search(answer or ""))
    if not checks["no_lab_interpretation"]:
        fixes.append(
            "Не интерпретируй анализы и результаты — это делает врач на приёме. Предложи записаться "
            "к подходящему специалисту с результатами."
        )

    # 5. No invented booking confirmation / availability claims.
    checks["no_invented_availability"] = not bool(_AVAILABILITY_CLAIM_RE.search(answer or ""))
    if not checks["no_invented_availability"]:
        fixes.append(
            "Не подтверждай запись на конкретное время и не утверждай, что есть свободные окна — "
            "время подтверждает администратор. Скажи, что передашь заявку и администратор свяжется."
        )

    # 6. Contact request must target the adult client, not the child.
    checks["no_child_contact_request"] = not bool(_CHILD_CONTACT_RE.search(answer or ""))
    if not checks["no_child_contact_request"]:
        fixes.append(
            "Не проси номер или контакт ребёнка. Контакт нужен у взрослого: "
            "«Оставьте, пожалуйста, ваше имя и WhatsApp/телефон для связи»."
        )

    # 7. No invented doctors. Prefix matching tolerates case declensions
    # («врачу Руслану Киму» must still match Руслан/Ким from the KB).
    known_names = kb_doctor_names()
    known_stems = tuple(name[: max(3, len(name) - 2)] for name in known_names)
    unknown_doctor = False
    for match in _DOCTOR_MENTION_RE.finditer(answer or ""):
        tokens = match.group(1).split()
        if tokens and not any(tok.startswith(stem) for tok in tokens for stem in known_stems):
            unknown_doctor = True
            break
    checks["no_invented_doctor"] = not unknown_doctor
    if unknown_doctor:
        fixes.append(
            "Не называй врачей, которых нет в базе знаний. Используй только врачей из базы "
            "или скажи, что подходящего специалиста уточнит администратор."
        )

    # 8. No unsupported promotions (only 10% pensioners / 5% family card).
    promo_unsupported = bool(_UNSUPPORTED_PROMO_RE.search(answer or ""))
    pct_unsupported = any(
        (m.group(1) or m.group(2) or "") not in _KB_DISCOUNT_PCTS
        for m in _DISCOUNT_PCT_RE.finditer(answer or "")
    )
    checks["no_invented_promotion"] = not (promo_unsupported or pct_unsupported)
    if not checks["no_invented_promotion"]:
        fixes.append(
            "Не упоминай рассрочку, промокоды, бонусы или скидки, которых нет в базе. В базе только "
            "скидка пенсионерам 10% (будни до 13:00) и семейная карта 5%. Остальное уточнит администратор."
        )

    # 9. Price asked -> KB price present OR an honest admin handoff.
    if intent in _PRICE_INTENTS:
        checks["price_present_when_asked"] = bool(answer_money) or "администратор" in low
        if not checks["price_present_when_asked"]:
            fixes.append(
                "Пользователь спросил цену — назови конкретную сумму из базы знаний; если её нет "
                "в базе, честно скажи, что уточнит администратор."
            )

    # 10. No treatment-result guarantees. An honest DISCLAIMER of guarantees is
    # scrubbed first, so it never trips the check (live regression: the honest
    # "гарантий не даёт ни одна клиника" answer was replaced with the meta
    # fallback, and the guarantee question got no real answer).
    scrubbed = _NEGATED_GUARANTEE_RE.sub(" ", answer or "")
    checks["no_guarantees"] = not bool(_GUARANTEE_RE.search(scrubbed))
    if not checks["no_guarantees"]:
        fixes.append(
            "Убери гарантии результата лечения. Итог оценивает врач — не обещай выздоровление. "
            "Честно скажи, что гарантий результата не даёт ни одна клиника, и предложи первичный приём."
        )

    # 11a. Compact length.
    word_count = len((answer or "").split())
    if intent not in _WORDCOUNT_EXEMPT_INTENTS:
        checks["compact_length_ok"] = word_count <= _WORD_LIMIT
        if not checks["compact_length_ok"]:
            fixes.append(
                f"Ответ слишком длинный ({word_count} слов). "
                "Перепиши короче: 2–4 предложения, без повторов."
            )
    else:
        checks["compact_length_ok"] = True

    # 11b. No verbose bullet list.
    bullet_count = len(_LIST_LINE_RE.findall(answer or ""))
    if intent not in _LISTCOUNT_EXEMPT_INTENTS:
        checks["no_verbose_list"] = bullet_count <= 3
        if not checks["no_verbose_list"]:
            fixes.append(
                "Убери длинный маркированный список. Ответь кратко: 2–4 предложения без списков."
            )
    else:
        checks["no_verbose_list"] = True

    # 11c. No vague filler.
    filler = [p for p in _FORBIDDEN_PHRASES if p in low]
    checks["no_filler"] = not filler
    if filler:
        fixes.append("Убери шаблонные фразы и говори конкретикой.")

    # 12. No premature contact push.
    do_not_ask_list = planner.get("do_not_ask") or []
    if "contact" in do_not_ask_list or intent == "offensive":
        contact_push = "contact" in detect_asked_slots(answer)
        checks["no_premature_contact_push"] = not contact_push
        if contact_push:
            fixes.append(
                "Не запрашивай контакт — пользователь не готов записываться. "
                "Ответь по существу без запроса WhatsApp/телефона."
            )

    # 13. No re-asking a known slot.
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

    # 14. No repeated greeting.
    if state.greeting_already_sent:
        greeted = bool(_GREETING_RE.search(answer or ""))
        checks["no_repeated_greeting"] = not greeted
        if greeted:
            fixes.append(
                "Убери приветствие — разговор уже идёт. Начни сразу с ответа по существу."
            )

    # 15. No booking CTA while the conversation is still in an emergency context.
    if state.urgency_flag == "emergency" and intent in _EMERGENCY_CONTEXT_INTENTS:
        booking_push = bool(_BOOKING_PUSH_RE.search(answer or ""))
        checks["no_booking_cta_on_emergency"] = not booking_push
        if booking_push:
            fixes.append(
                "Не предлагай обычную запись — в разговоре звучали тревожные симптомы. "
                "Сначала срочная помощь (103/112); плановую запись предлагай только когда "
                "пользователь сам вернётся к ней."
            )

    return ValidationResult(failed=bool(fixes), fix=" ".join(fixes), checks=checks)


# ---------------------------------------------------------------------------
# Intent-aware safe fallback (never crashes, never invents facts)
# ---------------------------------------------------------------------------

_FALLBACK_MEDICAL_ADVICE = (
    "Я не врач и не могу назначать лечение, ставить диагноз или оценивать анализы дистанционно — "
    "это делает врач на приёме. Могу подсказать, к какому специалисту записаться, и передать "
    "заявку администратору."
)
_FALLBACK_PRICE = (
    "Чтобы не ошибиться с деталями, уточню точную информацию у администратора. "
    "Оставьте, пожалуйста, ваше имя и WhatsApp/телефон для связи — мы вернёмся с ответом."
)
_FALLBACK_DISCOUNT = (
    "Из постоянного: скидка пенсионерам 10% на консультации специалистов по будням до 13:00 "
    "и семейная карта 5% при четырёх и более визитах семьи в месяц. Других акций не обещаю — "
    "дополнительные условия уточнит администратор."
)
_FALLBACK_CONTACT = (
    "Хорошо! Оставьте, пожалуйста, ваше имя и WhatsApp/телефон для связи — администратор "
    "свяжется с вами и подтвердит удобное время приёма."
)
_FALLBACK_CONTACT_RECEIVED = (
    "Спасибо, контакт получен! Передаю заявку администратору — он свяжется с вами и подтвердит "
    "ближайшее доступное время приёма."
)
_FALLBACK_CONTACT_RECEIVED_ASK_DETAILS = (
    _FALLBACK_CONTACT_RECEIVED
    + " Подскажите, пожалуйста, как зовут пациента и сколько ему лет?"
)
_FALLBACK_ADMIN_HAS_CONTACT = (
    "Детали уточню у администратора — контакт у нас уже есть, свяжемся с вами и поможем "
    "подобрать подходящий вариант."
)
_FALLBACK_OBJECTION = (
    "Понимаю вас. Чтобы не решать вслепую, разумный первый шаг: первичный приём, где врач "
    "осмотрит и честно скажет, что действительно нужно, а что нет.\n\n"
    "Хотите, покажу ближайшие окна к подходящему специалисту?"
)
_FALLBACK_GENERAL = (
    "Подскажу детали точнее с помощью администратора. Оставьте, пожалуйста, ваше имя и "
    "WhatsApp/телефон для связи — мы свяжемся с вами и поможем."
)
_FALLBACK_OFFENSIVE = (
    "Я могу помочь с вопросами по записи, врачам и ценам MedNova Clinic. "
    "Если захотите продолжить — напишите."
)
_FALLBACK_SPECIALTY = (
    "Подскажу направление: опишите коротко, что беспокоит и возраст пациента — предложу "
    "подходящего специалиста из нашей клиники."
)


def build_safe_fallback(
    planner: dict,
    state: ConversationState | None = None,
    message: str = "",
) -> str:
    """Intent-aware safe answer used when generation/repair fails.

    Contact-aware: once the user has left a phone/Telegram, no fallback may ask
    for the contact again. Symptom-aware: a symptom message still routes to a
    specialist and asks one clarifying question instead of dumping to the admin,
    even when the planner degraded to a vague intent (e.g. an LLM timeout).
    """
    intent = (planner or {}).get("current_intent", "unknown")
    contact_known = bool(state is not None and getattr(state, "contact", ""))
    emergency = state is not None and getattr(state, "urgency_flag", "") == "emergency"

    if intent == "offensive":
        return _FALLBACK_OFFENSIVE
    if intent == "medical_advice_request":
        return _FALLBACK_MEDICAL_ADVICE
    if intent == "ask_discount":
        return _FALLBACK_DISCOUNT

    # Symptom routing (deterministic, routing-only): keep a degraded turn useful
    # instead of falling through to a generic "leave your contact" answer.
    if not contact_known and not emergency and intent not in ("contact", "wants_booking"):
        specialty = detect_symptom_specialty(message)
        if specialty:
            ask_age = state is None or not state.is_known("age")
            detail_q = "сколько лет пациенту и как давно беспокоит" if ask_age else "как давно беспокоит"
            return (
                f"При таких жалобах обычно помогает {specialty}. "
                f"Подскажите, пожалуйста, {detail_q}? Предложу подходящего "
                "специалиста и помогу записаться."
            )

    if intent in ("ask_specialty_advice", "symptom_description"):
        return _FALLBACK_SPECIALTY
    if intent in ("contact", "wants_booking"):
        if contact_known:
            ask_details = state is not None and not state.is_known("age")
            return (
                _FALLBACK_CONTACT_RECEIVED_ASK_DETAILS if ask_details
                else _FALLBACK_CONTACT_RECEIVED
            )
        return _FALLBACK_CONTACT
    if intent in ("objection", "price_objection", "correction"):
        return _FALLBACK_OBJECTION
    if intent in (
        "ask_price", "ask_all_prices", "ask_doctor", "ask_schedule",
        "ask_preparation", "ask_services",
    ):
        return _FALLBACK_ADMIN_HAS_CONTACT if contact_known else _FALLBACK_PRICE
    return _FALLBACK_ADMIN_HAS_CONTACT if contact_known else _FALLBACK_GENERAL
