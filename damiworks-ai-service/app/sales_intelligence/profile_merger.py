"""Business profile merge logic (§10.3).

Pure function: takes the current ``business_profile`` and analyzer signals, returns a NEW
merged profile without mutating the input. Precedence: explicit > inferred > default >
unknown. Null/unknown never overwrites; contradictions set ``conflict=True`` with notes.

``merge_llm_insights`` (Phase B1) merges LLM-extracted insights into the separate
``llm_insights`` sub-block — never mixed with the heuristic top-level fields, so a
hypothesis can never overwrite a heuristic fact of higher confidence.
"""
from __future__ import annotations

import copy
from typing import Any

from .defaults import new_field_value

_RANK = {"explicit": 3, "inferred": 2, "default": 1, "unknown": 0}

# LLM insight confidence band: "medium" — above client-facts defaults (0.3), below
# explicit user statements (0.8+). Stored under the standard "inferred" rank.
LLM_INSIGHT_CONFIDENCE = 0.6

# Keys of the llm_insights sub-block (mirrors extractor.INSIGHT_FIELDS; duplicated to
# keep profile_merger import-light).
LLM_INSIGHT_FIELDS = (
    "pain",
    "budget_signals",
    "urgency",
    "hidden_objection",
    "client_intent_vector",
    "stage",
)


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


def merge_llm_insights(
    business_profile: dict[str, Any],
    insights: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a new ``business_profile`` with LLM insights merged into ``llm_insights``.

    Insights live in a dedicated sub-block (standard wrapped-value shape, rank
    "inferred", confidence ``LLM_INSIGHT_CONFIDENCE`` = "medium"), so heuristic
    top-level fields with equal-or-higher confidence are never touched. Null/empty
    incoming values never overwrite; the same value keeps the higher-confidence
    wrapper; a different value wins as the fresher hypothesis (same provenance,
    recency matters) with a conflict note, mirroring ``_merge_scalar`` style.
    """
    merged = copy.deepcopy(business_profile) if isinstance(business_profile, dict) else {}
    if not isinstance(insights, dict):
        return merged

    block = merged.get("llm_insights")
    if not isinstance(block, dict):
        block = {}
    else:
        block = copy.deepcopy(block)

    for field in LLM_INSIGHT_FIELDS:
        value = insights.get(field)
        if value in (None, ""):
            # Rule 3: null/unknown never overwrites.
            continue
        incoming = new_field_value(
            value,
            confidence=LLM_INSIGHT_CONFIDENCE,
            source_text="llm_insight_extractor",
            extraction_type="inferred",
        )
        existing = block.get(field)
        if isinstance(existing, dict) and existing.get("value") not in (None, ""):
            if existing.get("value") == value:
                # Same hypothesis — keep the wrapper with the higher confidence.
                if float(existing.get("confidence") or 0.0) >= LLM_INSIGHT_CONFIDENCE:
                    continue
            else:
                # Different hypothesis at equal provenance — the fresher one wins.
                incoming["conflict"] = True
                incoming["conflict_notes"] = [f"{existing.get('value')!r} -> {value!r}"]
        block[field] = incoming

    merged["llm_insights"] = block
    return merged
