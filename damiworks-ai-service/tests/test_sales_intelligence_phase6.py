"""Phase 6 unit tests — microbusiness_helper + integration_discovery prompt behavior.

Pure Python, zero API calls. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase6.py -v
"""
from __future__ import annotations

import pytest

from app.sales_intelligence import compose_safe_mode_instruction
from app.sales_intelligence.question_budget import QUESTION_BUDGET_INSTRUCTION


def _compose(mode, **kw):
    return compose_safe_mode_instruction(conversation_mode=mode, **kw)


# ---------------------------------------------------------------------------
# microbusiness_helper
# ---------------------------------------------------------------------------

def test_1_microbusiness_applied():
    r = _compose("microbusiness_helper")
    assert r["applied"] is True
    assert r["mode"] == "microbusiness_helper"
    assert "микробизнес" in r["instruction"]
    assert "follow-up" in r["instruction"]


def test_2_microbusiness_avoids_enterprise_qualification():
    instr = _compose("microbusiness_helper")["instruction"]
    assert "Не спрашивай про CRM, маржу" in instr
    assert "без корпоративного словаря" in instr


def test_3_microbusiness_combines_with_budget_instruction():
    # api appends QUESTION_BUDGET_INSTRUCTION after the mode instruction when exhausted
    mode_instr = _compose("microbusiness_helper")["instruction"]
    combined = "\n\n".join([mode_instr, QUESTION_BUDGET_INSTRUCTION])
    assert "микробизнес" in combined
    assert "нельзя задавать ещё один квалификационный вопрос" in combined


def test_4_microbusiness_price_first_is_price_orientation():
    r = _compose("microbusiness_helper", wow_mechanism="checkout_or_call", next_best_action_type="price_orientation")
    assert r["applied"] is True
    assert "ценовой ориентир" in r["instruction"]
    assert "не запускай анкету" in r["instruction"]
    assert "price-first" in r["reason"]


# ---------------------------------------------------------------------------
# integration_discovery
# ---------------------------------------------------------------------------

def test_5_integration_applied():
    r = _compose("integration_discovery")
    assert r["applied"] is True
    assert r["mode"] == "integration_discovery"
    assert "интеграционный разбор" in r["instruction"]


def test_6_integration_focuses_on_architecture():
    instr = _compose("integration_discovery")["instruction"]
    assert "архитектуры" in instr
    assert "поток" in instr  # data flow
    assert "откуда приходит заявка" in instr


def test_7_integration_combines_with_budget_instruction():
    mode_instr = _compose("integration_discovery")["instruction"]
    combined = "\n\n".join([mode_instr, QUESTION_BUDGET_INSTRUCTION])
    assert "архитектуры" in combined
    assert "нельзя задавать ещё один квалификационный вопрос" in combined


def test_8_integration_price_first_does_not_fake_estimate():
    r = _compose("integration_discovery", wow_mechanism="checkout_or_call", next_best_action_type="price_orientation")
    assert r["applied"] is True
    assert "ценовой ориентир" in r["instruction"]
    assert "Не называй точную смету без scope" in r["instruction"]


# ---------------------------------------------------------------------------
# still-fallback modes
# ---------------------------------------------------------------------------

# After Phase 7 only roleplay_demo remains legacy fallback (light_roi/full_roi became enabled).
@pytest.mark.parametrize("mode", ["roleplay_demo"])
def test_9to11_non_enabled_modes_legacy_fallback(mode):
    r = _compose(mode)
    assert r["applied"] is False
    assert r["instruction"] == ""
    assert "legacy fallback" in r["reason"]


# ---------------------------------------------------------------------------
# roleplay no-op
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["microbusiness_helper", "integration_discovery"])
def test_12_roleplay_active_no_op(mode):
    r = _compose(mode, roleplay_active=True)
    assert r["applied"] is False
    assert "roleplay_active" in r["reason"]


# ---------------------------------------------------------------------------
# tenant override for the new modes
# ---------------------------------------------------------------------------

def test_tenant_override_microbusiness():
    r = _compose("microbusiness_helper", tenant_settings={"prompt_mode_microbusiness_helper": "ТЕНАНТ-МИКРО"})
    assert r["instruction"] == "ТЕНАНТ-МИКРО"


def test_tenant_override_integration():
    r = _compose("integration_discovery", tenant_settings={"prompt_mode_integration_discovery": "ТЕНАНТ-ИНТЕГР"})
    assert r["instruction"] == "ТЕНАНТ-ИНТЕГР"
