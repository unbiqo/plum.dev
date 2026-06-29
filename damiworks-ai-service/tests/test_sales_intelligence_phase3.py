"""Phase 3 unit tests — strengthened deterministic strategy/scoring/wow across client types.

Pure Python, zero API calls, shadow-only. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase3.py -v
"""
from __future__ import annotations

import pytest

from app.sales_intelligence import ensure_intelligence_metadata, run_intelligence_turn
from app.sales_intelligence.defaults import default_business_profile, new_field_value


def _turn(message: str, *, metadata=None, dialog_state=None):
    return run_intelligence_turn(
        enabled=True,
        message=message,
        chat_history=[],
        session_metadata=metadata or {},
        dialog_state=dialog_state or {},
    )


def _debug(message: str, **kw):
    return _turn(message, **kw)["debug"]


# ---------------------------------------------------------------------------
# 1–12: message-driven scenarios
# ---------------------------------------------------------------------------

def test_1_cold_lead():
    d = _debug("Что вы вообще делаете?")
    assert d["shadow_conversation_mode"] == "simple_explainer"
    assert d["shadow_wow_mechanism"] == "simple_explanation"


def test_2_microbusiness():
    d = _debug("Я сам отвечаю в WhatsApp, не успеваю")
    assert d["shadow_conversation_mode"] == "microbusiness_helper"
    assert d["shadow_wow_mechanism"] == "microbusiness_assistant_pitch"


def test_3_mature_smb():
    d = _debug("У нас 5 менеджеров, amoCRM и 100 заявок в день")
    assert d["shadow_conversation_mode"] == "full_roi_audit"
    assert d["shadow_wow_mechanism"] == "full_roi_audit"


def test_4_light_roi():
    d = _debug("У нас 20 заявок в день, средний чек 30к, менеджер иногда долго отвечает")
    assert d["shadow_conversation_mode"] in ("light_roi_diagnostic", "full_roi_audit")
    # logging must justify the choice
    assert any("data" in r or "flow" in r or "roi" in r.lower() for r in d["shadow_logging_reasons"])


def test_5_integration():
    d = _debug("Нужно связать WhatsApp, amoCRM, склад и оплату")
    assert d["shadow_conversation_mode"] == "integration_discovery"
    assert d["shadow_wow_mechanism"] == "integration_architecture_map"


def test_6_low_fit_no_business():
    d = _debug("У меня пока нет бизнеса, просто хочу посмотреть")
    assert d["shadow_conversation_mode"] in ("low_fit_nurture", "simple_explainer")
    assert d["shadow_conversation_mode"] != "full_roi_audit"


def test_7_irritated_user():
    d = _debug("Зачем столько вопросов?")
    assert d["shadow_conversation_mode"] in ("simple_explainer", "microbusiness_helper")
    g = d["shadow_bot_guidance"]
    assert g.get("should_simplify") is True
    assert g.get("should_stop_questioning") is True


def test_8_price_first():
    d = _debug("Сколько стоит?")
    assert d["shadow_conversation_mode"] == "simple_explainer"
    assert d["shadow_wow_mechanism"] == "checkout_or_call"
    assert d["shadow_next_best_action_type"] == "price_orientation"
    g = d["shadow_bot_guidance"]
    assert g.get("do_not_hard_close") is True
    assert g.get("do_not_show_checkout_card") is True


def test_9_roleplay_intent():
    d = _debug("Давай отыграем, как бот будет продавать мои услуги")
    assert d["shadow_conversation_mode"] == "roleplay_demo"
    assert d["shadow_wow_mechanism"] == "roleplay_demo"
    assert d["shadow_next_best_action_type"] == "offer_roleplay"


def test_10_anti_fit_tech_diy():
    d = _debug("Мне нужен open-source код, я сам разверну бесплатно")
    assert d["shadow_conversation_mode"] == "low_fit_nurture"
    assert d["shadow_wow_mechanism"] != "checkout_or_call"


def test_11_ambiguous_low_confidence():
    d = _debug("интересно")
    assert d["shadow_conversation_mode"] == "simple_explainer"


def test_12_high_integration_and_roi():
    d = _debug("У нас 200 лидов в день, amoCRM, склад, оплата и 10 менеджеров")
    # architecture complexity dominates -> integration_discovery wins over full_roi
    assert d["shadow_conversation_mode"] == "integration_discovery"
    assert any("integration" in r.lower() for r in d["shadow_logging_reasons"])


# ---------------------------------------------------------------------------
# 13–14: roleplay isolation + price after rich profile
# ---------------------------------------------------------------------------

def test_13_roleplay_active_skips_strategy():
    meta = ensure_intelligence_metadata({})
    meta["business_profile"]["business_niche"] = new_field_value("реальная ниша", extraction_type="explicit")
    meta["qualification_state"]["conversation_mode"] = "full_roi_audit"
    result = _turn("маржа 40%, 200 заказов", metadata=meta, dialog_state={"roleplay_demo_active": True})
    assert set(result["persist_blocks"]) == {"roleplay_state"}            # no business_profile update
    assert result["previous_b2b_conversation_mode_preserved"] is True
    assert result["debug"]["shadow_roleplay_isolation_active"] is True


def _rich_profile_metadata():
    bp = default_business_profile()
    bp["business_niche"] = new_field_value("интернет-магазин", confidence=0.8, extraction_type="explicit")
    bp["lead_volume_count"] = new_field_value(100, confidence=0.8, extraction_type="explicit")
    bp["lead_volume_period"] = new_field_value("day", confidence=0.7, extraction_type="explicit")
    bp["operators_count"] = new_field_value(5, confidence=0.85, extraction_type="explicit")
    bp["crm_or_tracking_tool"] = new_field_value("amoCRM", confidence=0.8, extraction_type="explicit")
    meta = ensure_intelligence_metadata({})
    meta["business_profile"] = bp
    return meta


def test_14_price_after_rich_profile():
    d = _debug("сколько будет стоить?", metadata=_rich_profile_metadata())
    assert d["shadow_conversation_mode"] == "full_roi_audit"
    assert d["shadow_wow_mechanism"] == "checkout_or_call"
    assert d["shadow_next_best_action_type"] in ("price_orientation", "offer_call_or_specification")


# ---------------------------------------------------------------------------
# Scoring properties
# ---------------------------------------------------------------------------

def test_high_confidence_facts_outweigh_low_confidence():
    from app.sales_intelligence.scoring import compute_scores

    high = default_business_profile()
    high["crm_or_tracking_tool"] = new_field_value("amoCRM", confidence=0.8, extraction_type="explicit")
    low = default_business_profile()
    low["crm_or_tracking_tool"] = new_field_value("amoCRM", confidence=0.3, extraction_type="default")
    behavior = {"friction_signals": []}
    assert compute_scores(high, behavior)["data_readiness_score"] > compute_scores(low, behavior)["data_readiness_score"]


def test_missing_data_is_not_low_fit():
    # empty profile + neutral message must not be classified low_fit
    d = _debug("расскажите подробнее про ваших агентов")
    assert d["shadow_conversation_mode"] != "low_fit_nurture"


def test_roleplay_demo_branch_does_not_overwrite_persisted_b2b_mode():
    # An established B2B session (full_roi_audit) expresses roleplay intent BEFORE the
    # simulation activates. The per-turn shadow mode is roleplay_demo, but the persisted
    # conversation_mode must stay full_roi_audit so previous_b2b_conversation_mode survives.
    meta = ensure_intelligence_metadata({})
    meta["qualification_state"]["conversation_mode"] = "full_roi_audit"
    result = _turn("давай отыграем продавца", metadata=meta)  # roleplay NOT active yet
    assert result["debug"]["shadow_conversation_mode"] == "roleplay_demo"
    assert result["persist_blocks"]["qualification_state"]["conversation_mode"] == "full_roi_audit"


def test_logging_reasons_contain_scores_and_drivers():
    d = _debug("У нас 5 менеджеров, amoCRM и 100 заявок в день")
    joined = " | ".join(d["shadow_logging_reasons"])
    assert "scores:" in joined
    assert "drivers:" in joined
