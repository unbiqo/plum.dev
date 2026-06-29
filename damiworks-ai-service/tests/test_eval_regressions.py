"""Manual-eval regression tests (post Adaptive Sales Intelligence v2).

Covers regressions A–E found in manual Telegram eval. Pure Python, no API/LLM.
Run from damiworks-ai-service/:
    pytest tests/test_eval_regressions.py -v
"""
from __future__ import annotations

import pytest

from app.api import (
    DOCUMENTS_SITE_ANSWER,
    START_GREETING_ANSWER,
    _is_document_request,
    _is_explicit_roleplay_command,
    _is_nonempty_qualification_answer,
)
from app.sales_intelligence import (
    compose_safe_mode_instruction,
    run_intelligence_turn,
    update_question_budget_after_answer,
    ensure_intelligence_metadata,
)
from app.sales_intelligence.commercial_policy import build_commercial_policy, detect_price_intent

_ENABLED = {
    "simple_explainer", "low_fit_nurture", "microbusiness_helper",
    "integration_discovery", "light_roi_diagnostic", "full_roi_audit", "roleplay_demo",
}


def _turn(message, metadata=None):
    return run_intelligence_turn(
        enabled=True, message=message, chat_history=[],
        session_metadata=metadata or {}, dialog_state={},
    )


# ---------------------------------------------------------------------------
# Regression A — these messages must not crash the intelligence layer
# ---------------------------------------------------------------------------

_A_MESSAGES = [
    "У меня маленький бизнес, я один всё делаю.",
    "Что он реально сможет делать?",
    "Интересно.",
    "А как это может работать в бизнесе?",
]


@pytest.mark.parametrize("message", _A_MESSAGES)
def test_A_no_crash_and_normal_mode(message):
    meta = ensure_intelligence_metadata({})
    t = _turn(message, meta)                      # must not raise
    for k, v in t["persist_blocks"].items():
        meta[k] = v
    d = t["debug"]
    assert d["shadow_conversation_mode"] in _ENABLED
    # post-answer budget update must not raise either
    upd = update_question_budget_after_answer(
        meta, "Мы делаем AI-сотрудника, который отвечает клиентам и не теряет заявки.",
        conversation_mode=d["shadow_conversation_mode"],
    )
    assert upd["skip_reason"] in (None, "roleplay_active")


@pytest.mark.parametrize("message", _A_MESSAGES)
def test_A_messages_are_not_portfolio_requests(message):
    assert _is_document_request(message) is False


# ---------------------------------------------------------------------------
# Regression B — portfolio fallback false positives
# ---------------------------------------------------------------------------

_B_FALSE = [
    "Ну примерно, мне просто понять порядок.",
    "У нас 5 менеджеров, amoCRM и примерно 100 заявок в день.",
    "Средний чек около 40 тысяч, конверсия примерно 8%.",
    "Маржа примерно 35%, часть заявок менеджеры теряют.",
]
_B_TRUE = ["покажите кейсы", "есть портфолио?", "покажите примеры работ", "демо есть?"]


@pytest.mark.parametrize("message", _B_FALSE)
def test_B_metrics_and_priblizitelno_not_portfolio(message):
    assert _is_document_request(message) is False


@pytest.mark.parametrize("message", _B_TRUE)
def test_B_explicit_portfolio_still_detected(message):
    assert _is_document_request(message) is True


# ---------------------------------------------------------------------------
# Regression C — irritated user must stop questioning, no scope/checkout
# ---------------------------------------------------------------------------

def test_C_irritated_user_stops_questioning():
    msg = "Зачем столько вопросов? Просто скажите, чем вы можете помочь."
    d = _turn(msg)["debug"]
    assert d["shadow_conversation_mode"] in ("simple_explainer", "microbusiness_helper")
    g = d["shadow_bot_guidance"]
    assert g.get("should_stop_questioning") is True
    assert g.get("should_simplify") is True
    assert _is_document_request(msg) is False  # not a portfolio request either


# ---------------------------------------------------------------------------
# Regression D — microbusiness must not push CRM early
# ---------------------------------------------------------------------------

def test_D_microbusiness_no_crm_pressure():
    msg = "У меня заявки идут в Instagram и WhatsApp, я сам отвечаю."
    d = _turn(msg)["debug"]
    assert d["shadow_conversation_mode"] == "microbusiness_helper"
    instr = compose_safe_mode_instruction(conversation_mode="microbusiness_helper")["instruction"]
    assert "Не спрашивай про CRM" in instr
    assert "без корпоративного словаря" in instr


def test_D_microbusiness_price_is_time_saving():
    msg = "сколько стоит?"
    p = build_commercial_policy(
        conversation_mode="microbusiness_helper",
        price_intent=detect_price_intent(msg),
    )
    assert p["commercial_angle"] == "time_saving"
    assert "экономи" in p["price_response_guidance"]


# ---------------------------------------------------------------------------
# Regression E — greeting must not overpromise
# ---------------------------------------------------------------------------

def test_E_greeting_no_unsupported_claims():
    g = START_GREETING_ANSWER
    assert "дожимать" not in g
    assert "окупят себя" not in g
    assert "за первую неделю" not in g
    # still explains the AI employee + offers a soft next step
    assert "AI-сотрудника" in g
    assert "тест-драйв" in g


# ---------------------------------------------------------------------------
# Regression F — placeholder portfolio URL must never appear in any answer
# ---------------------------------------------------------------------------

def test_F_documents_site_answer_no_placeholder_url():
    assert "your-portfolio.dev" not in DOCUMENTS_SITE_ANSWER
    assert "http" not in DOCUMENTS_SITE_ANSWER  # no hardcoded links at all


_F_ROLEPLAY_DEMO_REQUESTS = [
    "Покажи демо: побудь продавцом в нише доставки еды.",
    "побудь консультантом по моей нише",
    "Покажи демо: будь менеджером",
    "Давай отыграем: побудь продавцом",
]


@pytest.mark.parametrize("msg", _F_ROLEPLAY_DEMO_REQUESTS)
def test_F_roleplay_demo_not_treated_as_document_request(msg):
    # These messages contain "покажи демо" but are roleplay commands — must not be
    # intercepted by the document-request early return (which would emit the placeholder URL).
    assert _is_explicit_roleplay_command(msg) is True, (
        f"Expected roleplay command detection for: {msg!r}"
    )


_F_STILL_PORTFOLIO_REQUESTS = [
    "покажите кейсы",
    "есть портфолио?",
    "покажите примеры работ",
    "демо есть?",
    "что вы уже делали",
]


@pytest.mark.parametrize("msg", _F_STILL_PORTFOLIO_REQUESTS)
def test_F_plain_portfolio_requests_still_detected(msg):
    assert _is_document_request(msg) is True
    assert _is_explicit_roleplay_command(msg) is False


# ---------------------------------------------------------------------------
# Regression G — price questions must not be echoed as automation_goal_text
# ---------------------------------------------------------------------------

_G_PRICE_QUESTIONS = [
    "А сколько это будет стоить?",
    "сколько стоит?",
    "какая цена?",
    "какой бюджет нужен?",
    "скажите стоимость",
    "назовите прайс",
    "ценник?",
]


@pytest.mark.parametrize("msg", _G_PRICE_QUESTIONS)
def test_G_price_question_not_a_qualification_answer(msg):
    # Price questions must not be misclassified as qualification answers about automation
    # tasks — this would echo them into "В проект добавим: <price question>".
    assert _is_nonempty_qualification_answer(msg) is False, (
        f"Price question misclassified as qualification answer: {msg!r}"
    )


_G_REAL_QUALIFICATION_ANSWERS = [
    "Нужно квалифицировать клиентов и передавать горячих менеджеру",
    "ответы на вопросы и напоминания о брошенной корзине",
    "все задачи — прогрев, ответы и сбор заявок",
    "автоматизировать Instagram",
]


@pytest.mark.parametrize("msg", _G_REAL_QUALIFICATION_ANSWERS)
def test_G_real_qualification_answers_still_accepted(msg):
    assert _is_nonempty_qualification_answer(msg) is True
