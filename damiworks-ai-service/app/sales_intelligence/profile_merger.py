"""Business profile merge logic (§10.3).

Pure function: takes the current ``business_profile`` and analyzer signals, returns a NEW
merged profile without mutating the input. Precedence: explicit > inferred > default >
unknown. Null/unknown never overwrites; contradictions set ``conflict=True`` with notes.
"""
from __future__ import annotations

import copy
from typing import Any

_RANK = {"explicit": 3, "inferred": 2, "default": 1, "unknown": 0}


def _rank(field_value: dict[str, Any]) -> int:
    return _RANK.get(str(field_value.get("extraction_type")), 0)


def _is_empty(field_value: dict[str, Any] | None) -> bool:
    return not isinstance(field_value, dict) or field_value.get("value") in (None, "")


def _merge_scalar(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if _is_empty(incoming):
        # Rule 3: null/unknown never overwrites.
        return existing if isinstance(existing, dict) else copy.deepcopy(incoming)

    if _is_empty(existing):
        return copy.deepcopy(incoming)

    assert isinstance(existing, dict)
    if existing.get("value") == incoming.get("value"):
        # Same fact — keep the higher-provenance/confidence wrapper.
        winner = incoming if _rank(incoming) > _rank(existing) else existing
        merged = copy.deepcopy(winner)
        merged["confidence"] = max(
            float(existing.get("confidence") or 0.0), float(incoming.get("confidence") or 0.0)
        )
        return merged

    # Contradiction (rules 1, 2, 4).
    note = f"{existing.get('value')!r} -> {incoming.get('value')!r}"
    incoming_wins = _rank(incoming) > _rank(existing) or (
        _rank(incoming) == _rank(existing)
        and float(incoming.get("confidence") or 0.0) >= float(existing.get("confidence") or 0.0) + 0.2
    )
    winner = incoming if incoming_wins else existing
    merged = copy.deepcopy(winner)
    merged["conflict"] = True
    notes = list(merged.get("conflict_notes") or [])
    notes.append(note)
    merged["conflict_notes"] = notes
    return merged


def _merge_list(existing: list | None, incoming: list | None) -> list:
    result: list = list(existing or [])
    for item in incoming or []:
        if item not in result:
            result.append(item)
    return result


def merge_business_profile(business_profile: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Return a new ``business_profile`` with analyzer signals merged in (§10.3)."""
    merged = copy.deepcopy(business_profile) if isinstance(business_profile, dict) else {}

    for field, incoming in (analysis.get("profile_signals") or {}).items():
        if not isinstance(incoming, dict):
            continue
        merged[field] = _merge_scalar(merged.get(field), incoming)

    for field, incoming_list in (analysis.get("list_signals") or {}).items():
        merged[field] = _merge_list(merged.get(field), incoming_list)

    return merged
