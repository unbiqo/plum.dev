"""Question budget per conversation mode (§11.3).

Anti-questionnaire guard: each mode allows a limited number of *main qualification
questions* before the bot must deliver value. Only main qualification questions increment
``qualification_questions_asked_since_last_value`` (rhetorical/roleplay/follow-up/context-gate
questions do not). Phase 5 enforces the budget: it inspects the answer the bot just gave,
updates the persisted counter, and (via api.py) injects a "give value first" instruction when
the budget is exhausted.
"""
from __future__ import annotations

import re
from typing import Any

# Max main qualification questions before value, by conversation mode (§11.3).
MODE_QUESTION_LIMITS: dict[str, int] = {
    "simple_explainer": 1,
    "microbusiness_helper": 2,
    "light_roi_diagnostic": 3,
    "full_roi_audit": 5,
    "integration_discovery": 3,
    "roleplay_demo": 1,
    "low_fit_nurture": 1,  # spec says 0-1; cap at 1
}

DEFAULT_LIMIT = 1


def evaluate_budget(conversation_mode: str, prior_budget: dict[str, Any] | None) -> dict[str, int]:
    """Return the budget for ``conversation_mode`` given prior counters.

    Sets ``max_questions_before_value`` from the mode, preserves the prior asked-counter, and
    recomputes ``remaining_questions_before_value`` (never below 0).
    """
    max_questions = MODE_QUESTION_LIMITS.get(conversation_mode, DEFAULT_LIMIT)
    prior = prior_budget if isinstance(prior_budget, dict) else {}
    asked = int(prior.get("qualification_questions_asked_since_last_value") or 0)
    remaining = max(0, max_questions - asked)
    return {
        "max_questions_before_value": max_questions,
        "qualification_questions_asked_since_last_value": asked,
        "remaining_questions_before_value": remaining,
    }


def must_give_value(budget: dict[str, Any]) -> bool:
    """True when the qualification budget is exhausted (bot should give value, not ask)."""
    return int(budget.get("remaining_questions_before_value") or 0) <= 0


# --- Phase 5: enforcement ---------------------------------------------------

# Exact instruction injected when the budget is exhausted (task E).
QUESTION_BUDGET_INSTRUCTION = (
    "Сейчас нельзя задавать ещё один квалификационный вопрос. Сначала дай клиенту полезный "
    "вывод, пример, рекомендацию или объяснение на основе уже известного. После ценности можно "
    "задать максимум один мягкий вопрос, только если он действительно нужен."
)


def _norm(text: str) -> str:
    return (text or "").casefold().replace("ё", "е")


# Business/qualification topics — a question touching these counts (task B).
_QUAL_TOPIC_PATTERNS = (
    r"ниш[аеуи]", r"сфер[аеуы]\s+бизнес", r"чем\s+(?:вы\s+)?занимаетесь", r"что\s+(?:вы\s+)?продает",
    r"канал\w*\s+(?:продаж|заявок|клиент)", r"откуда\s+(?:идут|приходят|пишут)?\s*(?:клиент|заявк|лид)",
    r"где\s+(?:берете|получаете|собираете)\s*(?:клиент|заявк|лид)",
    r"(?:скольк[оа]|объ[её]м)[^?]{0,25}(?:заявок|лидов|обращени|клиент)",
    r"(?:заявок|лидов)\s+в\s+(?:день|недел|месяц)",
    r"crm|амосрм|amocrm|битрикс", r"чем\s+ведете\s+учет",
    r"команд\w*|менеджер\w*|сотрудник\w*|оператор\w*|сколько\s+(?:у\s+вас\s+)?человек",
    r"средн\w*\s+чек", r"какой\s+(?:у\s+вас\s+)?чек", r"конверси", r"маржинальн|маржа",
    r"бол[ьи]\b|узкое\s+место|что\s+(?:сейчас\s+)?(?:тормозит|мешает)\s+продаж|где\s+теряете",
    r"интеграц|какие\s+систем", r"бюджет\b|сроки\b|когда\s+планируете",
    r"кто\s+принимает\s+решени|\bлпр\b|вы\s+принимаете\s+решени",
)

# Confirmations / rhetorical — never count (task B).
_CONFIRMATION_PATTERNS = (
    r"правильно\s+понима", r"я\s+правильно", r"правильно\s+ли", r"\bверно\?", r"\bтак\?",
    r"все\s+верно", r"если\s+я\s+(?:вас\s+)?правильно",
)

# Roleplay / context-gate phrasing — never count (task B).
_GATE_ROLEPLAY_PATTERNS = (
    r"\bроль\b|отыгра|сыгра", r"каталог", r"\bскрин", r"прайс-?лист", r"\bpdf\b", r"\bфайл",
    r"опишите\s+(?:ваш\s+)?бизнес",
)

# next_best_action types whose purpose is to deliver value, not qualify (task C).
_VALUE_NBA = {
    "give_value", "offer_roleplay", "offer_light_roi", "offer_full_roi",
    "offer_integration_discovery", "price_orientation", "offer_call_or_specification",
    "simplify", "nurture", "answer_only",
}

# Text markers of delivered value (insight/recommendation/offer/price/comparison) — task C.
_VALUE_MARKERS = (
    r"рекоменд", r"совет", r"лучше\s+подойд", r"обычно\b", r"как\s+правило", r"окупа",
    r"например|к\s+примеру", r"смысл\s+в\s+том", r"это\s+поможет", r"покажу|тест-?драйв",
    r"давайте\s+разбер|разложу", r"порядка\b|вилка\b|от\s+\$?\d", r"стоит\s+(?:от|порядка)",
    r"сэконом", r"теряете\s+\w+", r"в\s+вашем\s+случае",
)


def _match_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def detect_main_qualification_question(
    answer_text: str,
    conversation_mode: str | None = None,
    roleplay_active: bool = False,
) -> bool:
    """True only if the assistant answer asks for business/qualification data (task B)."""
    if roleplay_active:
        return False
    text = _norm(answer_text)
    if "?" not in text:
        return False
    if _match_any(_GATE_ROLEPLAY_PATTERNS, text):
        return False
    if _match_any(_CONFIRMATION_PATTERNS, text):
        return False
    return _match_any(_QUAL_TOPIC_PATTERNS, text)


def detect_value_delivered(
    answer_text: str,
    conversation_mode: str | None = None,
    wow_mechanism: str | None = None,
    next_best_action: str | None = None,
) -> bool:
    """True if the assistant answer delivered clear value (task C)."""
    if next_best_action in _VALUE_NBA:
        return True
    return _match_any(_VALUE_MARKERS, _norm(answer_text))


def update_question_budget_after_answer(
    metadata: dict[str, Any],
    answer_text: str,
    *,
    conversation_mode: str | None = None,
    wow_mechanism: str | None = None,
    next_best_action: str | None = None,
    roleplay_active: bool = False,
) -> dict[str, Any]:
    """Update the persisted question_budget counter from the answer the bot just gave.

    Mutates ``metadata['qualification_state']['question_budget']`` in place. Returns a summary
    dict (budget + detection flags + skip_reason) for logging. Roleplay turns are a no-op.
    """
    qual_state = metadata.get("qualification_state")
    if not isinstance(qual_state, dict):
        qual_state = {}
        metadata["qualification_state"] = qual_state
    budget = qual_state.get("question_budget")
    if not isinstance(budget, dict):
        budget = {
            "max_questions_before_value": MODE_QUESTION_LIMITS.get(conversation_mode or "", DEFAULT_LIMIT),
            "qualification_questions_asked_since_last_value": 0,
            "remaining_questions_before_value": MODE_QUESTION_LIMITS.get(conversation_mode or "", DEFAULT_LIMIT),
        }

    if roleplay_active:
        return {
            "budget": budget,
            "qualification_detected": False,
            "value_detected": False,
            "skip_reason": "roleplay_active",
        }

    max_q = int(budget.get("max_questions_before_value") or DEFAULT_LIMIT)
    counter = int(budget.get("qualification_questions_asked_since_last_value") or 0)

    qualification = detect_main_qualification_question(answer_text, conversation_mode, roleplay_active)
    value = detect_value_delivered(answer_text, conversation_mode, wow_mechanism, next_best_action)

    if qualification:
        counter += 1
    elif value:
        counter = 0

    new_budget = {
        "max_questions_before_value": max_q,
        "qualification_questions_asked_since_last_value": counter,
        "remaining_questions_before_value": max(0, max_q - counter),
    }
    qual_state["question_budget"] = new_budget
    return {
        "budget": new_budget,
        "qualification_detected": qualification,
        "value_detected": value,
        "skip_reason": None,
    }
