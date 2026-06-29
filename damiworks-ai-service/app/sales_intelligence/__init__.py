"""Sales Intelligence layer (project_specs.md v1.2).

Phase 1: metadata schemas + read-only shadow profiler.
Phase 2: persistence of the new metadata blocks + two-level timeout + roleplay/B2B isolation.

Public API:
- ``run_intelligence_turn`` — pure turn computation (debug + persist_blocks + previous-mode).
- ``run_shadow_profiler`` — backward-compatible Phase 1 entry point (debug only).
- ``ensure_intelligence_metadata`` — non-destructive v1.2 metadata migration.
- ``apply_intelligence_timeouts`` / reset helpers — two-level session timeout.
"""
from __future__ import annotations

from .commercial_policy import (
    build_commercial_policy,
    detect_close_intent,
    detect_price_intent,
)
from .defaults import ensure_intelligence_metadata
from .prompt_composer import ENABLED_MODES, compose_safe_mode_instruction
from .question_budget import (
    QUESTION_BUDGET_INSTRUCTION,
    must_give_value,
    update_question_budget_after_answer,
)
from .roi_engine import build_roi_result
from .roi_readiness import assess_roi_readiness
from .schemas import ConversationMode, WowMechanism
from .shadow_profiler import run_intelligence_turn, run_shadow_profiler
from .timeouts import (
    B2B_INTELLIGENCE_TIMEOUT_HOURS,
    ROLEPLAY_TIMEOUT_HOURS,
    apply_intelligence_timeouts,
    reset_b2b_intelligence_blocks,
    reset_roleplay_state_block,
)

__all__ = [
    "run_intelligence_turn",
    "run_shadow_profiler",
    "compose_safe_mode_instruction",
    "ENABLED_MODES",
    "update_question_budget_after_answer",
    "must_give_value",
    "QUESTION_BUDGET_INSTRUCTION",
    "build_roi_result",
    "assess_roi_readiness",
    "build_commercial_policy",
    "detect_price_intent",
    "detect_close_intent",
    "ensure_intelligence_metadata",
    "apply_intelligence_timeouts",
    "reset_b2b_intelligence_blocks",
    "reset_roleplay_state_block",
    "ROLEPLAY_TIMEOUT_HOURS",
    "B2B_INTELLIGENCE_TIMEOUT_HOURS",
    "ConversationMode",
    "WowMechanism",
]
