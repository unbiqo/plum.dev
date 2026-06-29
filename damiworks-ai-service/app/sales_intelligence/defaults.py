"""Default factories + non-destructive metadata migration for Sales Intelligence v1.2.

All factories return plain JSONB-friendly dicts. ``ensure_intelligence_metadata`` only
*adds* missing blocks and never deletes or overwrites existing keys, so it is safe to run
against legacy ``chat_sessions.metadata``. In Phase 1 the caller (shadow profiler) runs it
against a deepcopy, so nothing is persisted.
"""
from __future__ import annotations

from typing import Any

from .schemas import ExtractionType, SCORE_KEYS

SCHEMA_VERSION = "1.2"

# business_profile scalar fields stored as wrapped values (§8.4 / §10.2).
_PROFILE_SCALAR_FIELDS: tuple[str, ...] = (
    "business_niche",
    "offer_type",
    "geography_or_timezone",
    "lead_volume_count",
    "lead_volume_period",
    "average_check",
    "currency",
    "conversion_rate",
    "gross_margin",
    "operators_count",
    "owner_involved",
    "crm_or_tracking_tool",
    "response_time",
    "working_hours_coverage",
    "after_hours_leads",
    "missed_leads_estimate",
    "repetitive_questions_share",
    "qualification_needed",
    "capacity_constraint",
    "decision_maker_role",
    "urgency",
    "budget_sensitivity",
)

# business_profile list fields (§8.4).
_PROFILE_LIST_FIELDS: tuple[str, ...] = (
    "lead_channels",
    "main_pains",
    "lost_reasons",
    "integration_needs",
    "data_sources_available",
)

# Top-level metadata blocks owned by the intelligence layer (§8.1).
INTELLIGENCE_BLOCK_KEYS: tuple[str, ...] = (
    "business_profile",
    "qualification_state",
    "roi_state",
    "conversation_behavior",
    "roleplay_state",
)


def new_field_value(
    value: Any = None,
    *,
    confidence: float = 0.0,
    source_text: str | None = None,
    extraction_type: ExtractionType = "unknown",
    last_updated_at: str | None = None,
) -> dict[str, Any]:
    """Build a wrapped extracted field value (§8.2)."""
    return {
        "value": value,
        "confidence": confidence,
        "source_text": source_text,
        "extraction_type": extraction_type,
        "last_updated_at": last_updated_at,
        "conflict": False,
        "conflict_notes": [],
    }


def default_business_profile() -> dict[str, Any]:
    profile: dict[str, Any] = {field: new_field_value() for field in _PROFILE_SCALAR_FIELDS}
    for field in _PROFILE_LIST_FIELDS:
        profile[field] = []
    return profile


def default_scores() -> dict[str, int]:
    return {key: 0 for key in SCORE_KEYS}


def default_question_budget() -> dict[str, int]:
    # simple_explainer baseline: max 1 question before value (§11.3).
    return {
        "max_questions_before_value": 1,
        "qualification_questions_asked_since_last_value": 0,
        "remaining_questions_before_value": 1,
    }


def default_qualification_state() -> dict[str, Any]:
    return {
        "conversation_mode": "simple_explainer",
        "wow_mechanism": "simple_explanation",
        "scores": default_scores(),
        "question_budget": default_question_budget(),
        "last_value_given_at": None,
        "last_question_target_field": None,
        "last_next_best_action": None,
        "logging_reasons": [],
    }


def default_roi_state() -> dict[str, Any]:
    return {
        "roi_depth": "none",
        "last_roi_result": None,
        "last_shown_to_user_at": None,
        "assumptions": [],
        "missing_fields": [],
        "calculation_confidence": "low",
    }


def default_conversation_behavior() -> dict[str, Any]:
    return {
        "friction_signals": [],
        "engagement_level": "unknown",
        "user_answer_style": "unknown",
        "asked_price": False,
        "asked_how_it_works": False,
        "asked_for_demo": False,
        "explicit_commercial_intent": False,
        "irritated_by_questions": False,
    }


def default_roleplay_state() -> dict[str, Any]:
    # Keeps the legacy roleplay_demo_* key names for backward compatibility (§8.8).
    return {
        "roleplay_demo_active": False,
        "roleplay_demo_topic": None,
        "roleplay_demo_awaiting_context": False,
        "roleplay_demo_context_summary": None,
        "roleplay_demo_context_source": None,
        "roleplay_demo_context_wait_count": 0,
        "roleplay_demo_no_file_fallback": False,
        "roleplay_started_at": None,
        "roleplay_last_active_at": None,
    }


_BLOCK_FACTORIES = {
    "business_profile": default_business_profile,
    "qualification_state": default_qualification_state,
    "roi_state": default_roi_state,
    "conversation_behavior": default_conversation_behavior,
    "roleplay_state": default_roleplay_state,
}

# Legacy client_facts -> business_profile field mapping (§8 / Phase 2 compatibility).
_CLIENT_FACTS_MAP: tuple[tuple[str, str], ...] = (
    ("business_sphere", "business_niche"),
    ("crm_or_stack", "crm_or_tracking_tool"),
    ("automation_goal", "offer_type"),
)


def reflect_client_facts_into_profile(
    business_profile: dict[str, Any],
    client_facts: dict[str, Any],
) -> None:
    """Reflect obvious legacy ``client_facts`` into a freshly created ``business_profile``.

    Only fills empty scalar fields; uses ``extraction_type="default"`` with low confidence
    so a real extractor (Phase 3) can override later. Mutates ``business_profile`` in place.
    """
    if not isinstance(client_facts, dict):
        return

    for src_key, dst_key in _CLIENT_FACTS_MAP:
        raw = client_facts.get(src_key)
        value = str(raw).strip() if raw is not None else ""
        if not value:
            continue
        wrapped = business_profile.get(dst_key)
        if isinstance(wrapped, dict) and wrapped.get("value") in (None, ""):
            business_profile[dst_key] = new_field_value(
                value,
                confidence=0.3,
                source_text=value,
                extraction_type="default",
            )

    lead_channel = client_facts.get("lead_channel")
    channel = str(lead_channel).strip() if lead_channel is not None else ""
    if channel and not business_profile.get("lead_channels"):
        business_profile["lead_channels"] = [channel]


def ensure_intelligence_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Return metadata with all v1.2 intelligence blocks present.

    Non-destructive: never removes or overwrites existing keys. Operates on a shallow copy
    of the top-level dict; existing nested blocks are left as-is. Legacy ``client_facts`` are
    reflected into ``business_profile`` only when that block is created fresh.
    """
    result: dict[str, Any] = dict(meta) if isinstance(meta, dict) else {}

    created_business_profile = False
    for key in INTELLIGENCE_BLOCK_KEYS:
        if not isinstance(result.get(key), dict):
            result[key] = _BLOCK_FACTORIES[key]()
            if key == "business_profile":
                created_business_profile = True

    if created_business_profile:
        reflect_client_facts_into_profile(
            result["business_profile"],
            result.get("client_facts") or {},
        )

    migration = result.get("migration")
    if not isinstance(migration, dict):
        migration = {}
    migration.setdefault("schema_version", SCHEMA_VERSION)
    result["migration"] = migration

    return result
