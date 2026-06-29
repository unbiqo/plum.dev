"""Phase 1 unit tests — Sales Intelligence metadata + shadow profiler.

Pure Python, zero API calls. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_shadow.py -v
"""
from __future__ import annotations

import copy

import pytest

from app.sales_intelligence import ensure_intelligence_metadata, run_shadow_profiler
from app.sales_intelligence.defaults import (
    INTELLIGENCE_BLOCK_KEYS,
    default_business_profile,
    default_question_budget,
    new_field_value,
)
from app.sales_intelligence.profile_merger import merge_business_profile
from app.sales_intelligence.scoring import compute_scores
from app.sales_intelligence.signal_analyzer import analyze_signals
from app.sales_intelligence.strategy_engine import resolve_strategy


def _shadow(message: str, *, metadata=None, dialog_state=None, enabled=True):
    return run_shadow_profiler(
        enabled=enabled,
        message=message,
        chat_history=[],
        session_metadata=metadata or {},
        dialog_state=dialog_state or {},
    )


# ---------------------------------------------------------------------------
# Metadata initialization / migration
# ---------------------------------------------------------------------------

def test_ensure_creates_all_blocks_with_defaults():
    meta = ensure_intelligence_metadata({})
    for key in INTELLIGENCE_BLOCK_KEYS:
        assert isinstance(meta[key], dict)
    assert meta["qualification_state"]["conversation_mode"] == "simple_explainer"
    assert meta["roi_state"]["roi_depth"] == "none"
    assert meta["migration"]["schema_version"] == "1.2"


def test_ensure_is_idempotent_and_non_destructive():
    original = {"client_facts": {"business_sphere": "пиццерия"}, "custom_legacy_key": 42}
    once = ensure_intelligence_metadata(original)
    twice = ensure_intelligence_metadata(copy.deepcopy(once))
    assert once == twice
    # existing keys preserved
    assert once["client_facts"] == {"business_sphere": "пиццерия"}
    assert once["custom_legacy_key"] == 42


def test_ensure_reflects_client_facts_into_business_profile():
    meta = ensure_intelligence_metadata(
        {"client_facts": {"business_sphere": "детейлинг", "crm_or_stack": "amoCRM", "lead_channel": "instagram"}}
    )
    bp = meta["business_profile"]
    assert bp["business_niche"]["value"] == "детейлинг"
    assert bp["business_niche"]["extraction_type"] == "default"
    assert bp["crm_or_tracking_tool"]["value"] == "amoCRM"
    assert "instagram" in bp["lead_channels"]


def test_ensure_does_not_overwrite_existing_business_profile():
    existing = default_business_profile()
    existing["business_niche"] = new_field_value("реальная ниша", confidence=0.9, extraction_type="explicit")
    meta = ensure_intelligence_metadata(
        {"business_profile": existing, "client_facts": {"business_sphere": "legacy"}}
    )
    # business_profile already present -> reflection must not run
    assert meta["business_profile"]["business_niche"]["value"] == "реальная ниша"


# ---------------------------------------------------------------------------
# Profile merger (§10.3)
# ---------------------------------------------------------------------------

def test_explicit_overwrites_inferred_and_flags_conflict():
    profile = default_business_profile()
    profile["operators_count"] = new_field_value(1, confidence=0.6, extraction_type="inferred")
    analysis = {
        "profile_signals": {
            "operators_count": new_field_value(5, confidence=0.85, extraction_type="explicit")
        },
        "list_signals": {},
    }
    merged = merge_business_profile(profile, analysis)
    assert merged["operators_count"]["value"] == 5
    assert merged["operators_count"]["conflict"] is True
    assert merged["operators_count"]["conflict_notes"]


def test_null_never_overwrites_existing():
    profile = default_business_profile()
    profile["business_niche"] = new_field_value("кофейня", confidence=0.8, extraction_type="explicit")
    analysis = {"profile_signals": {"business_niche": new_field_value(None)}, "list_signals": {}}
    merged = merge_business_profile(profile, analysis)
    assert merged["business_niche"]["value"] == "кофейня"


# ---------------------------------------------------------------------------
# Roleplay isolation (hard requirement)
# ---------------------------------------------------------------------------

def test_roleplay_active_skips_profiling():
    debug = _shadow(
        "сколько стоит ваша пицца маргарита",
        dialog_state={"roleplay_demo_active": True},
    )
    assert debug["shadow_roleplay_isolation_active"] is True
    assert debug["shadow_extraction_skipped_reason"] == "roleplay_active"
    assert debug["shadow_wow_mechanism"] is None
    assert "roleplay isolation" in debug["shadow_logging_reasons"][0]


def test_roleplay_does_not_mutate_session_metadata():
    meta = {"business_profile": default_business_profile()}
    snapshot = copy.deepcopy(meta)
    _shadow("я владелец пиццерии, маржа 40%", metadata=meta, dialog_state={"roleplay_demo_active": True})
    assert meta == snapshot  # pure, no side effects


# ---------------------------------------------------------------------------
# Feature flag + purity
# ---------------------------------------------------------------------------

def test_disabled_flag_returns_minimal():
    assert _shadow("у нас 100 заявок", enabled=False) == {"intelligence_shadow_enabled": False}


def test_profiler_does_not_mutate_inputs():
    meta = {"client_facts": {"business_sphere": "автосервис"}}
    snapshot = copy.deepcopy(meta)
    _shadow("у нас 5 менеджеров и amoCRM, 100 заявок в день", metadata=meta)
    assert meta == snapshot


# ---------------------------------------------------------------------------
# Five canonical example classifications
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message, expected_mode",
    [
        ("я сам отвечаю в WhatsApp, не успеваю", "microbusiness_helper"),
        ("у нас 5 менеджеров и amoCRM, 100 заявок в день", "full_roi_audit"),
        ("просто интересно, что вы делаете", "simple_explainer"),
        ("сколько стоит?", "simple_explainer"),
    ],
)
def test_example_modes(message, expected_mode):
    debug = _shadow(message)
    assert debug["intelligence_shadow_enabled"] is True
    assert debug["shadow_conversation_mode"] == expected_mode


def test_microbusiness_example_wow():
    debug = _shadow("я сам отвечаю в WhatsApp, не успеваю")
    assert debug["shadow_wow_mechanism"] == "microbusiness_assistant_pitch"


def test_full_roi_example_wow():
    debug = _shadow("у нас 5 менеджеров и amoCRM, 100 заявок в день, платный трафик")
    assert debug["shadow_conversation_mode"] == "full_roi_audit"
    assert debug["shadow_wow_mechanism"] == "full_roi_audit"


# ---------------------------------------------------------------------------
# Price-first signal (cleanup): keep commercial signal, no hard close / card / questionnaire
# ---------------------------------------------------------------------------

def test_price_first_keeps_commercial_wow_without_questionnaire():
    debug = _shadow("сколько стоит?")
    assert debug["shadow_conversation_mode"] == "simple_explainer"
    assert debug["shadow_wow_mechanism"] == "checkout_or_call"
    assert debug["shadow_next_best_action_type"] == "price_orientation"


def test_price_first_bot_guidance_guardrails():
    behavior = analyze_signals("сколько стоит?")["behavior"]
    profile = default_business_profile()
    scores = compute_scores(profile, behavior)
    strategy = resolve_strategy(profile=profile, scores=scores, behavior=behavior)
    guidance = strategy["bot_guidance"]
    assert guidance["give_price_orientation_only"] is True
    assert guidance["do_not_hard_close"] is True
    assert guidance["do_not_show_checkout_card"] is True
    assert strategy["next_best_action"]["should_ask_now"] is False  # no questionnaire


# ---------------------------------------------------------------------------
# Question budget field rename
# ---------------------------------------------------------------------------

def test_question_budget_field_renamed():
    budget = default_question_budget()
    assert "qualification_questions_asked_since_last_value" in budget
    assert "questions_asked_since_last_value" not in budget
