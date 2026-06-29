"""Phase 2 unit tests — persistence, two-level timeout, roleplay/B2B isolation.

Pure Python, zero API calls. Run from damiworks-ai-service/:
    pytest tests/test_sales_intelligence_phase2.py -v
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

from app.sales_intelligence import (
    ensure_intelligence_metadata,
    reset_b2b_intelligence_blocks,
    reset_roleplay_state_block,
    run_intelligence_turn,
)
from app.sales_intelligence.timeouts import apply_intelligence_timeouts
from app.sales_intelligence.defaults import default_business_profile, new_field_value


def _turn(message: str, *, metadata=None, dialog_state=None, enabled=True):
    return run_intelligence_turn(
        enabled=enabled,
        message=message,
        chat_history=[],
        session_metadata=metadata or {},
        dialog_state=dialog_state or {},
    )


def _hours_ago(h: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


# ---------------------------------------------------------------------------
# Migration / compatibility
# ---------------------------------------------------------------------------

def test_legacy_metadata_migrates_and_preserves_unknown_keys():
    legacy = {
        "dialog_state": {"pain_expressed": True},
        "client_facts": {"business_sphere": "цветы"},
        "weird_unknown_key": {"x": 1},
    }
    meta = ensure_intelligence_metadata(copy.deepcopy(legacy))
    assert meta["business_profile"]["business_niche"]["value"] == "цветы"
    assert meta["dialog_state"] == {"pain_expressed": True}      # legacy preserved
    assert meta["client_facts"] == {"business_sphere": "цветы"}  # legacy preserved
    assert meta["weird_unknown_key"] == {"x": 1}                 # unknown preserved


def test_ensure_idempotent():
    once = ensure_intelligence_metadata({"client_facts": {"crm_or_stack": "amoCRM"}})
    twice = ensure_intelligence_metadata(copy.deepcopy(once))
    assert once == twice


def test_legacy_client_facts_still_present():
    meta = ensure_intelligence_metadata({"client_facts": {"business_sphere": "склад"}})
    assert "client_facts" in meta
    assert meta["client_facts"]["business_sphere"] == "склад"


# ---------------------------------------------------------------------------
# Two-level timeout
# ---------------------------------------------------------------------------

def test_timeout_none_under_6h():
    meta = ensure_intelligence_metadata({})
    meta["business_profile"]["business_niche"] = new_field_value("кофе", extraction_type="explicit")
    snapshot = copy.deepcopy(meta)
    applied = apply_intelligence_timeouts(meta, _hours_ago(2), reset_context=False)
    assert applied == "none"
    assert meta == snapshot


def test_timeout_roleplay_only_between_6h_and_72h():
    meta = ensure_intelligence_metadata({})
    meta["business_profile"]["business_niche"] = new_field_value("кофе", extraction_type="explicit")
    meta["roleplay_state"]["roleplay_demo_active"] = True
    applied = apply_intelligence_timeouts(meta, _hours_ago(10), reset_context=False)
    assert applied == "roleplay_only"
    # roleplay reset, B2B profile intact
    assert meta["roleplay_state"]["roleplay_demo_active"] is False
    assert meta["business_profile"]["business_niche"]["value"] == "кофе"


def test_timeout_b2b_after_72h_resets_b2b_keeps_legacy():
    meta = ensure_intelligence_metadata({"dialog_state": {"pain_expressed": True}, "extra": 7})
    meta["business_profile"]["business_niche"] = new_field_value("кофе", extraction_type="explicit")
    meta["qualification_state"]["conversation_mode"] = "full_roi_audit"
    applied = apply_intelligence_timeouts(meta, _hours_ago(80), reset_context=False)
    assert applied == "b2b"
    # B2B blocks reset to defaults
    assert meta["business_profile"]["business_niche"]["value"] is None
    assert meta["qualification_state"]["conversation_mode"] == "simple_explainer"
    assert meta["roleplay_state"]["roleplay_demo_active"] is False
    # legacy + unknown preserved
    assert meta["dialog_state"] == {"pain_expressed": True}
    assert meta["extra"] == 7


def test_timeout_reset_context_is_noop_here():
    meta = ensure_intelligence_metadata({})
    meta["business_profile"]["business_niche"] = new_field_value("кофе", extraction_type="explicit")
    snapshot = copy.deepcopy(meta)
    assert apply_intelligence_timeouts(meta, _hours_ago(99), reset_context=True) == "none"
    assert meta == snapshot


def test_reset_block_helpers_preserve_unknown_keys():
    meta = {"business_profile": {"x": 1}, "roleplay_state": {"y": 2}, "unknown": 9, "dialog_state": {"a": 1}}
    reset_b2b_intelligence_blocks(meta)
    reset_roleplay_state_block(meta)
    assert meta["unknown"] == 9
    assert meta["dialog_state"] == {"a": 1}
    assert meta["roleplay_state"]["roleplay_demo_active"] is False


# ---------------------------------------------------------------------------
# Persistence contract (run_intelligence_turn)
# ---------------------------------------------------------------------------

def test_b2b_turn_returns_persist_blocks():
    result = _turn("у нас 5 менеджеров и amoCRM, 100 заявок в день")
    blocks = result["persist_blocks"]
    assert set(blocks) == {"business_profile", "qualification_state", "conversation_behavior", "roi_state"}
    assert blocks["qualification_state"]["conversation_mode"] == "full_roi_audit"
    assert blocks["business_profile"]["operators_count"]["value"] == 5


def test_b2b_turn_does_not_mutate_input_metadata():
    meta = {"client_facts": {"business_sphere": "автосервис"}}
    snapshot = copy.deepcopy(meta)
    _turn("у нас 100 заявок в день и amoCRM", metadata=meta)
    assert meta == snapshot  # pure


def test_conversation_behavior_latches_asked_price():
    prior = ensure_intelligence_metadata({})
    prior["conversation_behavior"]["asked_price"] = True  # latched from an earlier turn
    result = _turn("расскажите про интеграции", metadata=prior)
    assert result["persist_blocks"]["conversation_behavior"]["asked_price"] is True


# ---------------------------------------------------------------------------
# Roleplay isolation
# ---------------------------------------------------------------------------

def test_roleplay_active_persists_only_roleplay_state():
    meta = ensure_intelligence_metadata({})
    meta["business_profile"]["business_niche"] = new_field_value("реальная ниша", extraction_type="explicit")
    result = _turn(
        "у меня пиццерия, маржа 40%, 200 заказов",  # B2C simulation chatter
        metadata=meta,
        dialog_state={"roleplay_demo_active": True},
    )
    blocks = result["persist_blocks"]
    assert set(blocks) == {"roleplay_state"}  # business_profile NOT written
    assert "business_profile" not in blocks


def test_roleplay_preserves_previous_b2b_conversation_mode():
    meta = ensure_intelligence_metadata({})
    meta["qualification_state"]["conversation_mode"] = "full_roi_audit"
    result = _turn("маржа 40%", metadata=meta, dialog_state={"roleplay_demo_active": True})
    assert result["previous_b2b_conversation_mode_preserved"] is True
    assert result["persist_blocks"]["roleplay_state"]["previous_b2b_conversation_mode"] == "full_roi_audit"


def test_roleplay_debug_marks_isolation():
    result = _turn("сколько стоит пицца", dialog_state={"roleplay_demo_active": True})
    assert result["debug"]["shadow_extraction_skipped_reason"] == "roleplay_active"
    assert result["debug"]["shadow_roleplay_isolation_active"] is True


# ---------------------------------------------------------------------------
# Roleplay exit isolation (simulated via the api helper contract)
# ---------------------------------------------------------------------------

def test_roleplay_exit_does_not_clear_business_profile():
    # mirrors api _clear_roleplay_state(dialog_state, session_metadata) on exit
    from app.api import _clear_roleplay_state

    session_metadata = ensure_intelligence_metadata({})
    session_metadata["business_profile"]["business_niche"] = new_field_value(
        "детейлинг", extraction_type="explicit"
    )
    dialog_state = {"roleplay_demo_active": True, "roleplay_demo_topic": "пицца"}
    _clear_roleplay_state(dialog_state, session_metadata)
    # roleplay cleared
    assert dialog_state["roleplay_demo_active"] is False
    assert session_metadata["roleplay_state"]["roleplay_demo_active"] is False
    # B2B profile survives
    assert session_metadata["business_profile"]["business_niche"]["value"] == "детейлинг"


def test_disabled_turn_returns_empty_persist():
    result = _turn("у нас 100 заявок", enabled=False)
    assert result["persist_blocks"] == {}
    assert result["debug"] == {"intelligence_shadow_enabled": False}
