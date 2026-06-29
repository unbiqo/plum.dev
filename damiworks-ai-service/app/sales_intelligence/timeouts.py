"""Two-level session timeout for the Sales Intelligence layer (§7 step 8).

Roleplay context and B2B intelligence have different lifetimes:
- roleplay simulation goes stale fast (6h) — clear only ``roleplay_state``;
- B2B intelligence lives much longer (72h) — only then reset the B2B blocks.

All resets are non-destructive to unrelated keys: legacy ``dialog_state``, ``client_facts``,
``migration`` and any unknown keys are preserved. (Legacy ``dialog_state`` keeps its existing
lifetime to avoid changing generation behavior — see plan.)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .defaults import (
    default_business_profile,
    default_conversation_behavior,
    default_qualification_state,
    default_roi_state,
    default_roleplay_state,
)

ROLEPLAY_TIMEOUT_HOURS = 6
B2B_INTELLIGENCE_TIMEOUT_HOURS = 72

_ROLEPLAY_TIMEOUT_SECONDS = ROLEPLAY_TIMEOUT_HOURS * 3600
_B2B_TIMEOUT_SECONDS = B2B_INTELLIGENCE_TIMEOUT_HOURS * 3600

# B2B intelligence blocks reset on the long timeout (NOT dialog_state / client_facts).
_B2B_BLOCK_FACTORIES = {
    "business_profile": default_business_profile,
    "qualification_state": default_qualification_state,
    "roi_state": default_roi_state,
    "conversation_behavior": default_conversation_behavior,
}


def reset_roleplay_state_block(meta: dict[str, Any]) -> None:
    """Reset only the roleplay_state block. Nothing else is touched."""
    meta["roleplay_state"] = default_roleplay_state()


def reset_b2b_intelligence_blocks(meta: dict[str, Any]) -> None:
    """Reset the four B2B intelligence blocks to defaults.

    Leaves ``dialog_state``, ``client_facts``, ``migration`` and any unknown keys intact.
    """
    for key, factory in _B2B_BLOCK_FACTORIES.items():
        meta[key] = factory()


def apply_intelligence_timeouts(
    meta: dict[str, Any],
    last_message_at: datetime | None,
    reset_context: bool,
) -> str:
    """Apply the two-level timeout in place. Returns ``none|roleplay_only|b2b``.

    ``reset_context`` and a missing ``last_message_at`` are no-ops here (reset is handled by the
    caller's ``clear_conversation_state`` + fresh re-initialization).
    """
    if reset_context or last_message_at is None:
        return "none"

    elapsed = (datetime.now(timezone.utc) - last_message_at).total_seconds()

    if elapsed >= _B2B_TIMEOUT_SECONDS:
        reset_b2b_intelligence_blocks(meta)
        reset_roleplay_state_block(meta)
        return "b2b"

    if elapsed >= _ROLEPLAY_TIMEOUT_SECONDS:
        reset_roleplay_state_block(meta)
        return "roleplay_only"

    return "none"
