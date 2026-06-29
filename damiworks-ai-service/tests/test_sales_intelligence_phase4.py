"""Phase 4 unit tests — prompt composer for safe modes only.

Pure Python, zero API calls. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase4.py -v
"""
from __future__ import annotations

import pytest

from app.sales_intelligence import compose_safe_mode_instruction


def _compose(mode, **kw):
    return compose_safe_mode_instruction(conversation_mode=mode, **kw)


# ---------------------------------------------------------------------------
# Safe modes -> instruction applied
# ---------------------------------------------------------------------------

def test_1_simple_explainer_applied():
    r = _compose("simple_explainer")
    assert r["applied"] is True
    assert r["mode"] == "simple_explainer"
    assert "простое объяснение" in r["instruction"]
    assert r["instruction"]


def test_2_low_fit_nurture_applied():
    r = _compose("low_fit_nurture")
    assert r["applied"] is True
    assert "nurture" in r["instruction"].lower()
    assert "не дожимай" in r["instruction"]


# ---------------------------------------------------------------------------
# Non-safe modes -> no-op / legacy fallback
# ---------------------------------------------------------------------------

# Only roleplay_demo stays legacy fallback after Phase 7.
# (micro/integration enabled in Phase 6; light_roi/full_roi enabled in Phase 7.)
@pytest.mark.parametrize("mode", ["roleplay_demo"])
def test_3to6_non_safe_modes_no_change(mode):
    r = _compose(mode)
    assert r["applied"] is False
    assert r["instruction"] == ""
    assert "legacy fallback" in r["reason"]


def test_none_mode_is_noop():
    r = _compose(None)
    assert r["applied"] is False
    assert r["instruction"] == ""


# ---------------------------------------------------------------------------
# Roleplay active -> no-op even for a safe mode
# ---------------------------------------------------------------------------

def test_7_roleplay_active_no_change():
    r = _compose("simple_explainer", roleplay_active=True)
    assert r["applied"] is False
    assert r["instruction"] == ""
    assert "roleplay_active" in r["reason"]


# ---------------------------------------------------------------------------
# Price-first simple_explainer -> price-orientation guidance only
# ---------------------------------------------------------------------------

def test_8_price_first_simple_explainer():
    r = _compose(
        "simple_explainer",
        wow_mechanism="checkout_or_call",
        next_best_action_type="price_orientation",
    )
    assert r["applied"] is True
    assert "ценовой ориентир" in r["instruction"]
    assert "карточк" in r["instruction"]      # explicitly forbids checkout card
    assert "Не дожимай" in r["instruction"]
    assert "price-first" in r["reason"]


def test_simple_explainer_without_price_is_standard():
    r = _compose("simple_explainer", wow_mechanism="simple_explanation", next_best_action_type="ask_simple_context_question")
    assert r["applied"] is True
    assert "ценовой ориентир" not in r["instruction"]  # standard, not price variant


# ---------------------------------------------------------------------------
# Tenant override
# ---------------------------------------------------------------------------

def test_tenant_override_used_when_present():
    r = _compose(
        "simple_explainer",
        tenant_settings={"prompt_mode_simple_explainer": "ТЕНАНТ-ИНСТРУКЦИЯ"},
    )
    assert r["instruction"] == "ТЕНАНТ-ИНСТРУКЦИЯ"


def test_tenant_override_price_first():
    r = _compose(
        "simple_explainer",
        wow_mechanism="checkout_or_call",
        next_best_action_type="price_orientation",
        tenant_settings={"prompt_mode_simple_explainer_price_first": "ЦЕНА-ТЕНАНТ"},
    )
    assert r["instruction"] == "ЦЕНА-ТЕНАНТ"
