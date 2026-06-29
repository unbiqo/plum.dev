"""Intelligence turn orchestrator (Phase 1 shadow + Phase 2 persistence).

``run_intelligence_turn`` is a pure function: it does not mutate the passed ``session_metadata``
(works on a deepcopy), does not call Supabase, does not call the LLM. It returns:

- ``debug``: the shadow fields logged into ``chat_logs.metadata.intelligence_shadow``;
- ``persist_blocks``: metadata blocks the caller may write back into ``chat_sessions.metadata``
  (Phase 2). Non-roleplay turns return B2B blocks; roleplay turns return only ``roleplay_state``
  (business_profile is never updated from roleplay messages — §7.1, §13.3, §21.8);
- ``previous_b2b_conversation_mode_preserved``: whether a prior B2B mode was carried into
  ``roleplay_state`` this turn.

``run_shadow_profiler`` remains as a thin, backward-compatible delegate returning ``debug`` only.

Later phases fold this logic into ``core/conversation_orchestrator.py``.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .defaults import default_scores, ensure_intelligence_metadata
from .profile_merger import merge_business_profile
from .roi_engine import build_roi_result
from .scoring import compute_scores
from .signal_analyzer import analyze_signals, should_run_llm_extraction
from .strategy_engine import resolve_strategy

# conversation_behavior boolean flags that latch True once observed in a session.
_BEHAVIOR_FLAGS = (
    "asked_price",
    "asked_how_it_works",
    "asked_for_demo",
    "explicit_commercial_intent",
    "irritated_by_questions",
)


def _disabled_result() -> dict[str, Any]:
    return {
        "debug": {"intelligence_shadow_enabled": False},
        "persist_blocks": {},
        "previous_b2b_conversation_mode_preserved": False,
    }


def _is_roleplay_active(dialog_state: dict[str, Any] | None, shadow_meta: dict[str, Any]) -> bool:
    if isinstance(dialog_state, dict) and dialog_state.get("roleplay_demo_active"):
        return True
    roleplay_state = shadow_meta.get("roleplay_state") or {}
    return bool(roleplay_state.get("roleplay_demo_active"))


def _update_conversation_behavior(prior: dict[str, Any], behavior: dict[str, Any]) -> dict[str, Any]:
    """Deterministically merge analyzer behavior onto the prior block (booleans latch True)."""
    updated = dict(prior) if isinstance(prior, dict) else {}
    for flag in _BEHAVIOR_FLAGS:
        updated[flag] = bool(updated.get(flag)) or bool(behavior.get(flag))
    signals = list(updated.get("friction_signals") or [])
    for sig in behavior.get("friction_signals") or []:
        if sig not in signals:
            signals.append(sig)
    updated["friction_signals"] = signals
    updated.setdefault("engagement_level", "unknown")
    updated.setdefault("user_answer_style", "unknown")
    return updated


_GUIDANCE_FLAGS = (
    "should_offer_roi_audit",
    "should_offer_roleplay",
    "should_offer_call",
    "should_simplify",
    "should_stop_questioning",
    "give_price_orientation_only",
    "do_not_hard_close",
    "do_not_show_checkout_card",
)


def _compact_guidance(guidance: dict[str, Any]) -> dict[str, Any]:
    """A small, log-safe summary of bot_guidance for chat_logs.metadata."""
    summary: dict[str, Any] = {"tone": guidance.get("tone")}
    for flag in _GUIDANCE_FLAGS:
        if guidance.get(flag):
            summary[flag] = True
    return summary


def _roi_state_from_result(roi_result: dict[str, Any]) -> dict[str, Any]:
    """Compact roi_state for persistence (§8.6, task I) — keeps the last result but no verbose text."""
    return {
        "roi_depth": roi_result["roi_depth"],
        "can_show_to_user": roi_result["can_show_to_user"],
        "calculation_confidence": roi_result["calculation_confidence"],
        "missing_fields": roi_result["missing_fields"],
        "assumptions": roi_result["assumptions"],
        "last_roi_result": {
            "scenarios": roi_result["scenarios"],
            "user_safe_summary": roi_result["user_safe_summary"],
        },
        "computed_at": roi_result["computed_at"],
    }


def _update_qualification_state(prior: dict[str, Any], strategy: dict[str, Any]) -> dict[str, Any]:
    """Write strategy outputs into qualification_state, preserving prior bookkeeping fields.

    Invariant: the persisted ``conversation_mode`` is always a real B2B depth mode — the
    "where to return after roleplay" anchor. ``roleplay_demo`` is a transient intent branch
    (visible per-turn in shadow debug) and must never overwrite the persisted B2B mode, or
    ``previous_b2b_conversation_mode`` would lose the real mode on roleplay entry.
    """
    updated = dict(prior) if isinstance(prior, dict) else {}
    mode = strategy["conversation_mode"]
    if mode != "roleplay_demo":
        updated["conversation_mode"] = mode
    else:
        updated.setdefault("conversation_mode", "simple_explainer")
    updated["wow_mechanism"] = strategy["wow_mechanism"]
    updated["scores"] = strategy["scores"]
    updated["question_budget"] = strategy["question_budget"]
    updated["last_next_best_action"] = strategy["next_best_action"]["type"]
    updated["logging_reasons"] = strategy["logging_reasons"]
    updated.setdefault("last_value_given_at", None)
    updated.setdefault("last_question_target_field", None)
    return updated


def run_intelligence_turn(
    *,
    enabled: bool,
    message: str,
    chat_history: list | None,
    session_metadata: dict[str, Any] | None,
    dialog_state: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute the intelligence turn (see module docstring). Pure — no side effects."""
    if not enabled:
        return _disabled_result()

    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Work strictly on a copy — never mutate caller state.
    shadow_meta = ensure_intelligence_metadata(copy.deepcopy(session_metadata or {}))
    qualification_state = shadow_meta.get("qualification_state") or {}

    if _is_roleplay_active(dialog_state, shadow_meta):
        # Roleplay isolation: do not read roleplay messages, do not update business_profile.
        prior_roleplay = dict(shadow_meta.get("roleplay_state") or {})
        existing_prev = prior_roleplay.get("previous_b2b_conversation_mode")
        preserved_mode = existing_prev or qualification_state.get("conversation_mode")
        prior_roleplay["roleplay_demo_active"] = True
        prior_roleplay["roleplay_last_active_at"] = now_iso
        prior_roleplay.setdefault("roleplay_started_at", now_iso)
        prior_roleplay["previous_b2b_conversation_mode"] = preserved_mode

        debug = {
            "intelligence_shadow_enabled": True,
            "shadow_conversation_mode": preserved_mode,
            "shadow_wow_mechanism": None,
            "shadow_scores": qualification_state.get("scores") or default_scores(),
            "shadow_roi_depth": (shadow_meta.get("roi_state") or {}).get("roi_depth", "none"),
            "shadow_next_best_action_type": None,
            "shadow_question_budget": qualification_state.get("question_budget"),
            "shadow_logging_reasons": [
                "roleplay isolation: profiler skipped, business_profile untouched"
            ],
            "shadow_extraction_skipped_reason": "roleplay_active",
            "shadow_roleplay_isolation_active": True,
            "shadow_bot_guidance": None,
        }
        return {
            "debug": debug,
            "persist_blocks": {"roleplay_state": prior_roleplay},
            "previous_b2b_conversation_mode_preserved": bool(preserved_mode),
            "roi_result": None,  # ROI never runs in roleplay (§12.1, hard-limit #11)
        }

    should_run, skip_reason = should_run_llm_extraction(message, chat_history)
    analysis = analyze_signals(message, chat_history)
    merged_profile = merge_business_profile(shadow_meta.get("business_profile") or {}, analysis)
    scores = compute_scores(merged_profile, analysis["behavior"])
    strategy = resolve_strategy(
        profile=merged_profile,
        scores=scores,
        behavior=analysis["behavior"],
        prior_qualification_state=qualification_state,
    )

    # Phase 1 never calls the LLM extractor; record why it was not run.
    extraction_skipped_reason = "phase1_llm_disabled" if should_run else skip_reason

    # Phase 7: deterministic ROI (Python only). Never runs in roleplay (handled above).
    roi_result = build_roi_result(
        merged_profile,
        scores,
        analysis["behavior"],
        conversation_mode=strategy["conversation_mode"],
        roleplay_active=False,
        now=now,
    )

    debug = {
        "intelligence_shadow_enabled": True,
        "shadow_conversation_mode": strategy["conversation_mode"],
        "shadow_wow_mechanism": strategy["wow_mechanism"],
        "shadow_scores": strategy["scores"],
        "shadow_roi_depth": roi_result["roi_depth"],
        "shadow_roi_can_show_to_user": roi_result["can_show_to_user"],
        "shadow_roi_confidence": roi_result["calculation_confidence"],
        "shadow_next_best_action_type": strategy["next_best_action"]["type"],
        "shadow_question_budget": strategy["question_budget"],
        "shadow_logging_reasons": strategy["logging_reasons"],
        "shadow_extraction_skipped_reason": extraction_skipped_reason,
        "shadow_roleplay_isolation_active": False,
        "shadow_bot_guidance": _compact_guidance(strategy["bot_guidance"]),
    }
    persist_blocks = {
        "business_profile": merged_profile,
        "qualification_state": _update_qualification_state(qualification_state, strategy),
        "conversation_behavior": _update_conversation_behavior(
            shadow_meta.get("conversation_behavior") or {}, analysis["behavior"]
        ),
        "roi_state": _roi_state_from_result(roi_result),
    }
    return {
        "debug": debug,
        "persist_blocks": persist_blocks,
        "previous_b2b_conversation_mode_preserved": False,
        "roi_result": roi_result,
    }


def run_shadow_profiler(
    *,
    enabled: bool,
    message: str,
    chat_history: list | None,
    session_metadata: dict[str, Any] | None,
    dialog_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Backward-compatible Phase 1 entry point: returns the shadow ``debug`` dict only."""
    return run_intelligence_turn(
        enabled=enabled,
        message=message,
        chat_history=chat_history,
        session_metadata=session_metadata,
        dialog_state=dialog_state,
    )["debug"]
