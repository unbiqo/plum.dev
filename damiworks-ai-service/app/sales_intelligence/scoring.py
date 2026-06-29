"""Heuristic scoring (§11.1-11.2), 0-100 scale.

Phase 3 deterministic slice — no LLM. Scores are derived from the merged business_profile and
current-turn behavior flags. High-confidence facts contribute more than inferred/default ones
(``_weight``). Missing data does NOT push scores toward low-fit — low fit is decided by
explicit anti-fit signals in the strategy engine, not by absent data.
"""
from __future__ import annotations

import re
from typing import Any


def _field(profile: dict[str, Any], name: str) -> dict[str, Any] | None:
    fv = profile.get(name)
    return fv if isinstance(fv, dict) else None


def _value(profile: dict[str, Any], field: str) -> Any:
    fv = _field(profile, field)
    return fv.get("value") if fv else None


def _has(profile: dict[str, Any], field: str) -> bool:
    return _value(profile, field) not in (None, "")


def _confidence(profile: dict[str, Any], field: str) -> float:
    fv = _field(profile, field)
    try:
        return float(fv.get("confidence") or 0.0) if fv else 0.0
    except (TypeError, ValueError):
        return 0.0


def _weight(profile: dict[str, Any], field: str) -> float:
    """Contribution multiplier by confidence: explicit facts count more than inferred/default."""
    if not _has(profile, field):
        return 0.0
    c = _confidence(profile, field)
    if c >= 0.8:
        return 1.0
    if c >= 0.6:
        return 0.85
    if c >= 0.4:
        return 0.6
    if c > 0:
        return 0.4
    return 0.5  # value present but unscored confidence -> neutral-ish


def _num(profile: dict[str, Any], field: str) -> int | None:
    raw = _value(profile, field)
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    if raw is None:
        return None
    m = re.search(r"\d{1,7}", str(raw))
    return int(m.group(0)) if m else None


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def compute_scores(profile: dict[str, Any], behavior: dict[str, Any]) -> dict[str, int]:
    channels = profile.get("lead_channels") or []
    pains = profile.get("main_pains") or []
    integrations = profile.get("integration_needs") or []
    data_sources = profile.get("data_sources_available") or []
    paid_traffic = "paid_traffic" in data_sources

    lead_volume = _num(profile, "lead_volume_count")
    operators = _num(profile, "operators_count")
    owner_involved = _value(profile, "owner_involved") is True
    has_check = _has(profile, "average_check")
    has_crm = _has(profile, "crm_or_tracking_tool")
    has_niche = _has(profile, "business_niche")

    w_check = _weight(profile, "average_check")
    w_crm = _weight(profile, "crm_or_tracking_tool")
    w_volume = _weight(profile, "lead_volume_count")
    w_operators = _weight(profile, "operators_count")

    # --- icp_fit_score ---
    icp = 0.0
    icp += 25 if has_niche else 0
    icp += 25 if (lead_volume or channels) else 0
    icp += 20 if pains else 0
    icp += 15 if channels else 0
    icp += 15 if (has_crm or integrations) else 0

    # --- roi_potential_score (numbers + team/CRM/paid + likely losses) ---
    roi = 0.0
    if lead_volume is not None:
        base = 35 if lead_volume >= 50 else 25 if lead_volume >= 15 else 12
        roi += base * (w_volume or 1.0)
    roi += 20 * w_check
    roi += 15 if paid_traffic else 0
    roi += 15 if any(p in pains for p in ("losing_leads", "slow_response")) else 0
    roi += 10 * w_crm
    roi += 8 if (operators is not None and operators >= 2) else 0

    # --- operational_pain_score (micro/owner pain lifts this + ai_fit, NOT roi) ---
    pain = 0.0
    pain += 25 if owner_involved else 0
    _pain_weights = {
        "not_enough_time": 20, "slow_response": 20, "owner_overload": 20,
        "forgetting_followups": 15, "chaos_in_chats": 15, "losing_leads": 15,
    }
    pain += sum(_pain_weights.get(p, 0) for p in pains)
    pain += 10 if (not has_crm and (lead_volume or channels or owner_involved)) else 0

    # --- data_readiness_score (knowing numbers/team/tooling) ---
    data = 0.0
    data += 25 * w_volume
    data += 25 * w_check
    data += 20 if _has(profile, "conversion_rate") else 0
    data += 15 if _has(profile, "gross_margin") else 0
    data += 15 * w_crm
    data += 10 * w_operators
    data += 5 if _has(profile, "lead_volume_period") else 0

    # --- conversation_friction_score ---
    friction = 0.0
    friction += 55 if behavior.get("irritated_by_questions") else 0
    only_price = behavior.get("asked_price") and not (pains or channels or lead_volume or has_crm)
    friction += 30 if only_price else 0
    friction += 10 * len(behavior.get("friction_signals") or [])

    # --- buying_readiness_score (price-first lifts commercial signal, no forced close) ---
    buying = 0.0
    buying += 30 if behavior.get("asked_price") else 0
    buying += 20 if behavior.get("asked_for_demo") else 0
    buying += 15 if any(p in pains for p in ("owner_overload", "losing_leads")) else 0
    buying += 15 if (owner_involved or _has(profile, "decision_maker_role")) else 0
    buying += 10 if (_value(profile, "urgency") in ("high", True)) else 0

    # --- ai_fit_score (repetitive/qualification/handoff/integration/high chat) ---
    ai = 0.0
    ai += 25 if pains else 0
    ai += 20 if integrations else 0
    ai += 10 * w_crm
    ai += 20 if (lead_volume is not None and lead_volume >= 30) else 0
    ai += 15 if channels else 0
    ai += 10 if _value(profile, "qualification_needed") is True else 0
    ai += 10 if owner_involved else 0

    # --- integration_complexity_score ---
    integ = 20 * len(integrations)
    if integrations and has_crm:
        integ += 20
    if integrations and (operators is not None and operators >= 3):
        integ += 10

    return {
        "icp_fit_score": _clamp(icp),
        "roi_potential_score": _clamp(roi),
        "operational_pain_score": _clamp(pain),
        "data_readiness_score": _clamp(data),
        "conversation_friction_score": _clamp(friction),
        "buying_readiness_score": _clamp(buying),
        "ai_fit_score": _clamp(ai),
        "integration_complexity_score": _clamp(integ),
    }
