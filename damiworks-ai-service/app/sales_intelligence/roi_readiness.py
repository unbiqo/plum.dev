"""ROI readiness gate (§12.2-12.6).

Decides which ROI depth is justified by the available data — none / rough_estimate /
light_roi / full_roi — plus a calculation_confidence and the list of missing fields. Pure,
deterministic, no LLM. ROI is never assessed for roleplay turns (§12.1, hard-limit #11).
"""
from __future__ import annotations

import re
from typing import Any

# Fields whose presence/confidence drive the gate.
_LEAKAGE_PAINS = ("losing_leads", "slow_response")
_TIME_PAINS = ("not_enough_time", "owner_overload", "chaos_in_chats", "forgetting_followups")


def _field(profile: dict[str, Any], name: str) -> dict[str, Any] | None:
    fv = profile.get(name)
    return fv if isinstance(fv, dict) else None


def _value(profile: dict[str, Any], name: str) -> Any:
    fv = _field(profile, name)
    return fv.get("value") if fv else None


def _present(profile: dict[str, Any], name: str) -> bool:
    return _value(profile, name) not in (None, "")


def _is_explicit(profile: dict[str, Any], name: str) -> bool:
    fv = _field(profile, name)
    if not fv or fv.get("value") in (None, ""):
        return False
    try:
        return float(fv.get("confidence") or 0.0) >= 0.6
    except (TypeError, ValueError):
        return False


def _num(profile: dict[str, Any], name: str) -> int | None:
    raw = _value(profile, name)
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    if raw is None:
        return None
    m = re.search(r"\d{1,9}", str(raw))
    return int(m.group(0)) if m else None


def _none_result(reason: str) -> dict[str, Any]:
    return {
        "level": "none",
        "calculation_confidence": "low",
        "confidence_reasons": [reason],
        "missing_fields": [],
    }


def assess_roi_readiness(
    profile: dict[str, Any],
    scores: dict[str, Any],
    behavior: dict[str, Any],
    *,
    conversation_mode: str | None = None,
    roleplay_active: bool = False,
) -> dict[str, Any]:
    """Return {level, calculation_confidence, confidence_reasons, missing_fields}."""
    if roleplay_active:
        return _none_result("roleplay_active: ROI disabled")
    if conversation_mode == "low_fit_nurture":
        return _none_result("low_fit_nurture: ROI would be fake")
    if behavior.get("irritated_by_questions") or int(scores.get("conversation_friction_score") or 0) >= 50:
        return _none_result("high friction: not the moment for ROI")

    pains = profile.get("main_pains") or []
    lead_volume = _num(profile, "lead_volume_count")
    has_lead = lead_volume is not None
    has_check = _present(profile, "average_check")
    has_conversion = _present(profile, "conversion_rate")
    has_margin = _present(profile, "gross_margin")
    leakage_signal = (
        _present(profile, "missed_leads_estimate")
        or _present(profile, "after_hours_leads")
        or _present(profile, "response_time")
        or any(p in pains for p in _LEAKAGE_PAINS)
    )
    operator_time_pain = (
        _value(profile, "owner_involved") is True
        or _present(profile, "operators_count")
        or any(p in pains for p in _TIME_PAINS)
    )

    missing: list[str] = []
    if not has_lead:
        missing.append("lead_volume")
    if not has_check:
        missing.append("average_check")
    if not has_conversion:
        missing.append("conversion_rate")
    if not has_margin:
        missing.append("gross_margin")
    if not leakage_signal:
        missing.append("leakage_or_missed_leads")

    if not (has_lead or leakage_signal or operator_time_pain):
        return {**_none_result("no lead volume / leakage / operator pain"), "missing_fields": missing}

    # full_roi — complete picture
    if has_lead and has_check and has_conversion and has_margin and leakage_signal:
        explicit_core = sum(
            _is_explicit(profile, f) for f in ("lead_volume_count", "average_check", "conversion_rate", "gross_margin")
        )
        confidence = "high" if explicit_core >= 3 else "medium"
        return {
            "level": "full_roi",
            "calculation_confidence": confidence,
            "confidence_reasons": [f"explicit core fields: {explicit_core}/4"],
            "missing_fields": missing,
        }

    # light_roi — lead + check (+ at least one of conversion/margin/leakage)
    if has_lead and has_check and (has_conversion or has_margin or leakage_signal):
        return {
            "level": "light_roi",
            "calculation_confidence": "medium",
            "confidence_reasons": ["lead volume + average check + partial signals"],
            "missing_fields": missing,
        }

    # rough_estimate — some volume / leakage / operator-time pain, but not enough for numbers
    return {
        "level": "rough_estimate",
        "calculation_confidence": "low",
        "confidence_reasons": ["partial data: qualitative range only"],
        "missing_fields": missing,
    }
