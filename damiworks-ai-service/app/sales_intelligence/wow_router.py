"""Wow Mechanism Router (§4).

Chooses the mechanism that creates the biggest wow this turn — a separate axis from
``conversation_mode``. Strong per-turn signals (roleplay/demo intent, price intent, integration
needs) override; otherwise it falls back to a mechanism fitting the mode. The result is clamped
to an allowed mode×mechanism matrix (e.g. ``low_fit_nurture`` can never be ``checkout_or_call``).
"""
from __future__ import annotations

from typing import Any

# Fallback mechanism per conversation mode (§4.2 alignment).
_MODE_WOW_FALLBACK = {
    "simple_explainer": "simple_explanation",
    "microbusiness_helper": "microbusiness_assistant_pitch",
    "light_roi_diagnostic": "light_roi_audit",
    "full_roi_audit": "full_roi_audit",
    "integration_discovery": "integration_architecture_map",
    "roleplay_demo": "roleplay_demo",
    "low_fit_nurture": "nurture",
}

# Allowed mechanisms per mode. A computed mechanism outside this set is clamped to the fallback.
_ALLOWED = {
    "simple_explainer": {"simple_explanation", "roleplay_demo", "checkout_or_call", "nurture"},
    "microbusiness_helper": {
        "microbusiness_assistant_pitch", "roleplay_demo", "checkout_or_call",
        "light_roi_audit", "simple_explanation",
    },
    "light_roi_diagnostic": {"light_roi_audit", "roleplay_demo", "checkout_or_call", "simple_explanation"},
    "full_roi_audit": {"full_roi_audit", "checkout_or_call", "roleplay_demo"},
    "integration_discovery": {"integration_architecture_map", "checkout_or_call", "roleplay_demo"},
    "roleplay_demo": {"roleplay_demo"},
    "low_fit_nurture": {"nurture", "simple_explanation"},  # never checkout_or_call
}


def _candidate(profile: dict[str, Any], scores: dict[str, int], conversation_mode: str, behavior: dict[str, Any]) -> str:
    integrations = profile.get("integration_needs") or []

    # explicit roleplay / demo intent
    if behavior.get("roleplay_intent") or behavior.get("asked_for_demo"):
        return "roleplay_demo"
    # price intent keeps the commercial signal (hard-close prevented by bot_guidance)
    if behavior.get("asked_price"):
        return "checkout_or_call"
    # explicit internal integration needs
    if integrations:
        return "integration_architecture_map"
    # otherwise a mechanism fitting the mode
    return _MODE_WOW_FALLBACK.get(conversation_mode, "simple_explanation")


def resolve_wow_mechanism(
    profile: dict[str, Any],
    scores: dict[str, int],
    conversation_mode: str,
    behavior: dict[str, Any],
) -> str:
    """Return a wow mechanism value (§4.1), clamped to the allowed mode×mechanism matrix."""
    candidate = _candidate(profile, scores, conversation_mode, behavior)
    allowed = _ALLOWED.get(conversation_mode, {"simple_explanation"})
    if candidate not in allowed:
        candidate = _MODE_WOW_FALLBACK.get(conversation_mode, "simple_explanation")
    return candidate
