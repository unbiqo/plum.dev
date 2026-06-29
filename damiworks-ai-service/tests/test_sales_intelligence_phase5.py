"""Phase 5 unit tests — question_budget enforcement.

Pure Python, zero API calls. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase5.py -v
"""
from __future__ import annotations

from app.sales_intelligence import ensure_intelligence_metadata, must_give_value
from app.sales_intelligence.question_budget import (
    detect_main_qualification_question,
    detect_value_delivered,
    evaluate_budget,
    update_question_budget_after_answer,
)


def _meta_with_mode(mode: str, *, asked: int = 0):
    meta = ensure_intelligence_metadata({})
    meta["qualification_state"]["conversation_mode"] = mode
    meta["qualification_state"]["question_budget"] = evaluate_budget(
        mode, {"qualification_questions_asked_since_last_value": asked}
    )
    return meta


def _ask(meta, answer, *, mode, nba=None, wow=None, roleplay=False):
    return update_question_budget_after_answer(
        meta, answer, conversation_mode=mode, wow_mechanism=wow, next_best_action=nba, roleplay_active=roleplay
    )


QUAL_Q = "А сколько у вас заявок в день и какая CRM?"
VALUE_A = "В вашем случае AI обычно окупается за счёт того, что ни один диалог не теряется. Например, ночные заявки он подхватывает сам."


# ---------------------------------------------------------------------------
# 1–3: budget exhaustion by mode
# ---------------------------------------------------------------------------

def test_1_microbusiness_two_questions_exhausts():
    meta = _meta_with_mode("microbusiness_helper")
    _ask(meta, QUAL_Q, mode="microbusiness_helper", nba="ask_business_context")
    r = _ask(meta, "А какой средний чек у вас?", mode="microbusiness_helper", nba="ask_business_context")
    assert r["qualification_detected"] is True
    assert must_give_value(r["budget"]) is True  # 2 of 2 used


def test_2_simple_explainer_one_question_exhausts():
    meta = _meta_with_mode("simple_explainer")
    r = _ask(meta, QUAL_Q, mode="simple_explainer", nba="ask_simple_context_question")
    assert must_give_value(r["budget"]) is True  # 1 of 1


def test_3_full_roi_allows_up_to_five():
    meta = _meta_with_mode("full_roi_audit")
    for i in range(4):
        r = _ask(meta, QUAL_Q, mode="full_roi_audit", nba="ask_metric_for_roi")
        assert must_give_value(r["budget"]) is False, f"exhausted too early at {i+1}"
    r = _ask(meta, QUAL_Q, mode="full_roi_audit", nba="ask_metric_for_roi")
    assert must_give_value(r["budget"]) is True  # 5th


# ---------------------------------------------------------------------------
# 4: value resets
# ---------------------------------------------------------------------------

def test_4_value_delivered_resets_counter():
    meta = _meta_with_mode("simple_explainer")
    _ask(meta, QUAL_Q, mode="simple_explainer", nba="ask_simple_context_question")
    assert must_give_value(meta["qualification_state"]["question_budget"]) is True
    r = _ask(meta, VALUE_A, mode="simple_explainer", nba="give_value")
    assert r["value_detected"] is True
    assert r["budget"]["qualification_questions_asked_since_last_value"] == 0
    assert must_give_value(r["budget"]) is False


# ---------------------------------------------------------------------------
# 5: roleplay no update
# ---------------------------------------------------------------------------

def test_5_roleplay_does_not_update_budget():
    meta = _meta_with_mode("full_roi_audit", asked=3)
    before = dict(meta["qualification_state"]["question_budget"])
    r = _ask(meta, QUAL_Q, mode="full_roi_audit", nba="ask_metric_for_roi", roleplay=True)
    assert r["skip_reason"] == "roleplay_active"
    assert meta["qualification_state"]["question_budget"] == before  # unchanged


# ---------------------------------------------------------------------------
# 6–8: detection rules
# ---------------------------------------------------------------------------

def test_6_price_orientation_not_qualification():
    # a price-orientation question about scope is not qualifying business data
    assert detect_main_qualification_question("Сориентирую по цене — какой примерный объём задачи?") is False
    # but if it asks qualifying business data, it counts
    assert detect_main_qualification_question("Чтобы посчитать, сколько у вас заявок в день?") is True


def test_7_confirmation_does_not_count():
    assert detect_main_qualification_question("Правильно понимаю?") is False
    assert detect_main_qualification_question("Я правильно понимаю, что у вас amoCRM?") is False


def test_8_context_gate_question_does_not_count():
    gate_q = "Пришлите PDF-каталог, скрин прайса или опишите ваш бизнес, чтобы я отыграл роль продавца."
    assert detect_main_qualification_question(gate_q) is False


def test_value_detection_by_nba_and_text():
    assert detect_value_delivered("любой текст", next_best_action="price_orientation") is True
    assert detect_value_delivered(VALUE_A, next_best_action="ask_metric_for_roi") is True  # text markers
    assert detect_value_delivered("А какая у вас ниша?", next_best_action="ask_business_context") is False


# ---------------------------------------------------------------------------
# 10: instruction only when exhausted
# ---------------------------------------------------------------------------

def test_10_budget_not_exhausted_when_remaining_positive():
    meta = _meta_with_mode("full_roi_audit")  # 5 max, 0 asked
    assert must_give_value(meta["qualification_state"]["question_budget"]) is False


def test_value_then_question_turn_keeps_enforcing():
    # asking a qualification question increments even if some value text present (conservative)
    meta = _meta_with_mode("simple_explainer")
    r = _ask(meta, VALUE_A + " А какая у вас ниша?", mode="simple_explainer", nba="ask_simple_context_question")
    assert r["qualification_detected"] is True
    assert must_give_value(r["budget"]) is True
