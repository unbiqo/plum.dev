"""Phase 7 unit tests — deterministic ROI engine + readiness gates + composer integration.

Pure Python, zero API calls, no LLM. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase7.py -v
"""
from __future__ import annotations

from app.sales_intelligence import build_roi_result, compose_safe_mode_instruction
from app.sales_intelligence.defaults import default_business_profile, new_field_value

_NO_FRICTION = {"conversation_friction_score": 0}
_CALM = {}


def _prof(**fields):
    p = default_business_profile()
    for key, val in fields.items():
        if isinstance(p.get(key), list):
            p[key] = val
        else:
            p[key] = new_field_value(val, confidence=0.8, extraction_type="explicit")
    return p


def _full_profile():
    return _prof(
        business_niche="интернет-магазин",
        lead_volume_count=100,
        lead_volume_period="day",
        average_check=30,          # -> ~30 000
        conversion_rate=15,        # -> 0.15
        gross_margin=40,           # -> 0.40
        missed_leads_estimate=20,  # leakage signal
        main_pains=["slow_response"],
    )


def _roi(profile, *, mode="full_roi_audit", roleplay=False, config=None, scores=None):
    return build_roi_result(
        profile, scores or _NO_FRICTION, _CALM, conversation_mode=mode, roleplay_active=roleplay, config=config
    )


# ---------------------------------------------------------------------------
# Readiness levels
# ---------------------------------------------------------------------------

def test_1_none_for_roleplay_active():
    r = _roi(_full_profile(), roleplay=True)
    assert r["roi_depth"] == "none"
    assert r["can_show_to_user"] is False


def test_2_none_for_simple_explainer_no_data():
    r = _roi(default_business_profile(), mode="simple_explainer")
    assert r["roi_depth"] == "none"
    assert r["can_show_to_user"] is False


def test_3_rough_estimate_lead_without_check():
    r = _roi(_prof(lead_volume_count=50, lead_volume_period="day", main_pains=["slow_response"]),
             mode="light_roi_diagnostic")
    assert r["roi_depth"] == "rough_estimate"
    assert r["can_show_to_user"] is False
    assert "average_check" in r["missing_fields"]


def test_4_light_roi_with_leads_and_check():
    r = _roi(_prof(lead_volume_count=20, lead_volume_period="day", average_check=30,
                   main_pains=["slow_response"]), mode="light_roi_diagnostic")
    assert r["roi_depth"] == "light_roi"
    assert r["can_show_to_user"] is True
    assert set(r["scenarios"]) == {"conservative", "realistic", "aggressive"}


def test_5_full_roi_with_complete_data():
    r = _roi(_full_profile())
    assert r["roi_depth"] == "full_roi"
    assert r["can_show_to_user"] is True
    assert r["calculation_confidence"] in ("medium", "high")
    sc = r["scenarios"]["realistic"]
    assert sc["lost_revenue"] is not None
    assert sc["recoverable_margin_profit"] is not None


# ---------------------------------------------------------------------------
# Formula safety
# ---------------------------------------------------------------------------

def test_6_negative_net_effect_handled():
    r = _roi(_full_profile(), config={"ai_monthly_cost": 10_000_000, "setup_cost": 500_000})
    sc = r["scenarios"]["conservative"]
    assert sc["payback_period_months"] is None  # net <= 0 -> no payback


def test_7_zero_ai_cost_handled():
    r = _roi(_full_profile(), config={"ai_monthly_cost": 0})
    for sc in r["scenarios"].values():
        assert sc["roi_percentage"] is None  # division by zero avoided


def test_8_missing_margin_in_assumptions():
    r = _roi(_prof(lead_volume_count=20, lead_volume_period="day", average_check=30,
                   main_pains=["slow_response"]), mode="light_roi_diagnostic")
    assert "gross_margin" in r["missing_fields"]
    assert any("маржин" in a for a in r["assumptions"])


def test_9_scenarios_generated():
    r = _roi(_full_profile())
    assert list(r["scenarios"]) == ["conservative", "realistic", "aggressive"]
    # realistic recoverable should be >= conservative (more optimistic knobs)
    cons = r["scenarios"]["conservative"]["recoverable_margin_profit"]
    aggr = r["scenarios"]["aggressive"]["recoverable_margin_profit"]
    assert aggr >= cons


def test_10_summary_uses_assumption_language():
    summary = _roi(_full_profile())["user_safe_summary"]
    assert "Грубая прикидка" in summary or "порядок цифр" in summary
    assert "вы точно теряете" not in summary
    assert "гарантированно" not in summary


def test_11_low_confidence_not_shown():
    r = _roi(_prof(lead_volume_count=50, lead_volume_period="day", main_pains=["slow_response"]),
             mode="light_roi_diagnostic")
    assert r["calculation_confidence"] == "low"
    assert r["can_show_to_user"] is False


def test_12_microbusiness_no_heavy_roi_without_data():
    r = _roi(_prof(owner_involved=True, main_pains=["not_enough_time"], lead_channels=["whatsapp"]),
             mode="microbusiness_helper")
    assert r["can_show_to_user"] is False  # no numbers -> no ROI


# ---------------------------------------------------------------------------
# Prompt composer integration
# ---------------------------------------------------------------------------

def test_13_composer_light_roi_only_when_can_show():
    roi_ok = _roi(_prof(lead_volume_count=20, lead_volume_period="day", average_check=30,
                        main_pains=["slow_response"]), mode="light_roi_diagnostic")
    r = compose_safe_mode_instruction(conversation_mode="light_roi_diagnostic", roi_result=roi_ok)
    assert r["applied"] is True
    assert "ROI-разбор" in r["instruction"]
    assert "Грубая прикидка" in r["instruction"]  # uses python summary


def test_14_composer_full_roi_only_when_can_show():
    roi_ok = _roi(_full_profile())
    r = compose_safe_mode_instruction(conversation_mode="full_roi_audit", roi_result=roi_ok)
    assert r["applied"] is True
    assert "Используй ТОЛЬКО эти посчитанные на Python цифры" in r["instruction"]
    assert "следующий шаг" in r["instruction"].lower()


def test_15_composer_metric_gap_when_cannot_show():
    roi_low = _roi(_prof(lead_volume_count=50, lead_volume_period="day", main_pains=["slow_response"]),
                   mode="light_roi_diagnostic")
    r = compose_safe_mode_instruction(conversation_mode="light_roi_diagnostic", roi_result=roi_low)
    assert r["applied"] is True
    assert "Данных недостаточно" in r["instruction"]
    assert "не показывай roi" in r["instruction"].lower()
    assert "can_show_to_user=false" in r["reason"]


def test_17_full_roi_price_first_is_price_orientation_not_roi_dump():
    roi_ok = _roi(_full_profile())
    r = compose_safe_mode_instruction(
        conversation_mode="full_roi_audit",
        wow_mechanism="checkout_or_call",
        next_best_action_type="price_orientation",
        roi_result=roi_ok,
    )
    assert "ценовой ориентир" in r["instruction"]
    assert "price-first" in r["reason"]


def test_roleplay_composer_noop_even_for_roi_mode():
    r = compose_safe_mode_instruction(conversation_mode="full_roi_audit", roleplay_active=True,
                                      roi_result=_roi(_full_profile()))
    assert r["applied"] is False
    assert "roleplay_active" in r["reason"]
