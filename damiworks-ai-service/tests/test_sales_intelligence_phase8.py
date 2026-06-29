"""Phase 8 unit tests — strategy-aware commercial / price policy.

Pure Python, zero API calls. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase8.py -v
"""
from __future__ import annotations

from app.sales_intelligence import (
    build_commercial_policy,
    detect_close_intent,
    detect_price_intent,
)

_ROI_SHOWABLE = {"can_show_to_user": True, "roi_depth": "full_roi"}
_ROI_HIDDEN = {"can_show_to_user": False, "roi_depth": "rough_estimate"}


def _policy(mode, **kw):
    kw.setdefault("price_intent", True)
    return build_commercial_policy(conversation_mode=mode, **kw)


# ---------------------------------------------------------------------------
# intent detection
# ---------------------------------------------------------------------------

def test_price_intent_detection():
    assert detect_price_intent("сколько стоит?") is True
    assert detect_price_intent("какая цена?") is True
    assert detect_price_intent("расскажите про агентов") is False


def test_close_intent_detection():
    assert detect_close_intent("хочу купить") is True
    assert detect_close_intent("давайте начнем") is True
    assert detect_close_intent("куда оплатить?") is True
    assert detect_close_intent("сколько стоит?") is False


# ---------------------------------------------------------------------------
# price behavior by mode
# ---------------------------------------------------------------------------

def test_1_cold_price_first_orientation_no_card():
    p = _policy("simple_explainer")
    assert p["should_show_price_orientation"] is True
    assert p["should_show_checkout_card"] is False
    assert p["max_questions"] == 1
    assert "Карточку заказа не показывай" in p["price_response_guidance"]
    assert p["commercial_angle"] == "scenario_orientation"


def test_2_microbusiness_price_time_saving():
    p = _policy("microbusiness_helper")
    assert p["commercial_angle"] == "time_saving"
    assert "экономи" in p["price_response_guidance"]
    assert "ROI" not in p["price_response_guidance"] or "тяжёлого ROI" in p["price_response_guidance"]
    assert p["should_avoid_hard_close"] is True


def test_3_integration_price_scope_no_fake_estimate():
    p = _policy("integration_discovery")
    assert p["commercial_angle"] == "integration_scope"
    assert "scope" in p["price_response_guidance"]
    assert "без выдуманной точной сметы" in p["price_response_guidance"]


def test_4_full_roi_price_uses_roi_when_can_show():
    p = _policy("full_roi_audit", roi_result=_ROI_SHOWABLE)
    assert p["should_use_roi_context"] is True
    assert p["commercial_angle"] == "roi_payback"
    assert "окупаемост" in p["price_response_guidance"]
    assert "Не гарантируй ROI" in p["price_response_guidance"]


def test_5_full_roi_price_no_roi_when_cannot_show():
    p = _policy("full_roi_audit", roi_result=_ROI_HIDDEN)
    assert p["should_use_roi_context"] is False
    assert p["commercial_angle"] == "roi_metric_gap"
    assert "Не показывай ROI-цифры" in p["price_response_guidance"]


def test_6_low_fit_price_no_hard_close():
    p = _policy("low_fit_nurture")
    assert p["should_avoid_hard_close"] is True
    assert p["commercial_angle"] == "no_pressure"
    assert "Не дожимай" in p["price_response_guidance"]


def test_7_post_roleplay_price_connects_to_demo():
    p = _policy("full_roi_audit", post_roleplay=True, roi_result=_ROI_SHOWABLE)
    assert p["commercial_angle"] == "post_roleplay"
    assert "демо" in p["price_response_guidance"]


# ---------------------------------------------------------------------------
# checkout / card safety
# ---------------------------------------------------------------------------

def test_8_explicit_close_intent_allows_card():
    p = _policy("simple_explainer", close_intent=True)
    assert p["should_show_checkout_card"] is True
    assert p["commercial_angle"] == "close_ready"
    assert p["max_questions"] == 0


def test_9_existing_close_state_preserved():
    p = _policy("microbusiness_helper", dialog_state={"close_consented": True})
    assert p["should_show_checkout_card"] is True


def test_10_bare_price_does_not_show_card():
    p = _policy("simple_explainer", close_intent=False, dialog_state={})
    assert p["should_show_checkout_card"] is False


# ---------------------------------------------------------------------------
# question_budget interaction
# ---------------------------------------------------------------------------

def test_12_budget_exhausted_no_questionnaire():
    p = _policy("microbusiness_helper", must_give_value_now=True)
    assert p["max_questions"] == 0
    assert p["should_ask_scope_question"] is False
    assert any("must_give_value_now" in r for r in p["logging_reasons"])


# ---------------------------------------------------------------------------
# roleplay isolation
# ---------------------------------------------------------------------------

def test_roleplay_active_policy_is_noop():
    p = build_commercial_policy(conversation_mode="full_roi_audit", price_intent=True, roleplay_active=True)
    assert p["price_response_guidance"] == ""
    assert p["should_answer_price"] is False


def test_no_price_intent_no_guidance():
    p = build_commercial_policy(conversation_mode="simple_explainer", price_intent=False)
    assert p["price_response_guidance"] == ""
    assert p["should_answer_price"] is False
