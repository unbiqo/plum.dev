"""Phase B1 — LLM insight extractor: unit tests + offline golden contract.

Pure Python, zero API calls (the LLM is always a mock). The opt-in live accuracy run
over the same golden dataset lives in ``tests/test_insight_extractor_live.py``.

Run from damiworks-ai-service/:
    pytest tests/test_insight_extractor.py -v
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from app.sales_intelligence import run_intelligence_turn
from app.sales_intelligence.defaults import new_field_value
from app.sales_intelligence.extractor import (
    INSIGHT_FIELDS,
    build_insight_prompt,
    extract_insights,
)
from app.sales_intelligence.profile_merger import (
    LLM_INSIGHT_CONFIDENCE,
    merge_llm_insights,
)

GOLDEN_PATH = Path(__file__).parent / "golden" / "insight_extractor_cases.yaml"

with GOLDEN_PATH.open(encoding="utf-8") as _fh:
    GOLDEN_CASES = yaml.safe_load(_fh)

_STRONG_MESSAGE = "У нас 5 менеджеров, amoCRM и 100 заявок в день"


def _fake_llm(payload):
    """Mock llm_call: returns the payload as JSON text (or the raw string as-is)."""
    async def fake(*, prompt, system_instruction):
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=False)
    return fake


def _extract(payload, *, message="Сообщение достаточной длины для гейта"):
    return asyncio.run(extract_insights(
        message=message,
        chat_history=[],
        business_profile=None,
        llm_call=_fake_llm(payload),
    ))


def _full_payload(**fields):
    """Full six-key schema payload: None everywhere except the given fields."""
    payload = {field: None for field in INSIGHT_FIELDS}
    payload.update(fields)
    return payload


# ---------------------------------------------------------------------------
# extract_insights — parsing contract (never raises)
# ---------------------------------------------------------------------------

def test_valid_json_returns_only_non_null_fields():
    result = _extract(_full_payload(
        pain="теряются заявки",
        urgency="High ",  # normalized (lower/strip)
        stage="decision",
    ))
    assert result == {"pain": "теряются заявки", "urgency": "high", "stage": "decision"}


def test_null_and_unknown_fields_are_dropped():
    result = _extract(_full_payload(urgency="unknown", stage="unknown"))
    assert result == {}


def test_invalid_json_returns_none():
    assert _extract("not json at all {") is None


def test_non_object_json_returns_none():
    assert _extract('["pain", "urgency"]') is None


def test_missing_required_keys_returns_none():
    assert _extract({"pain": "что-то болит"}) is None


def test_enum_outside_allowed_values_returns_none():
    assert _extract(_full_payload(urgency="critical")) is None
    assert _extract(_full_payload(stage="closing")) is None


def test_non_string_value_returns_none():
    assert _extract(_full_payload(pain=42)) is None


def test_extract_never_raises_on_llm_exception():
    async def boom(*, prompt, system_instruction):
        raise RuntimeError("LLM down")
    result = asyncio.run(extract_insights(
        message="хватает текста для гейта",
        chat_history=[],
        business_profile=None,
        llm_call=boom,
    ))
    assert result is None


# ---------------------------------------------------------------------------
# build_insight_prompt
# ---------------------------------------------------------------------------

def test_build_insight_prompt_includes_history_message_and_profile():
    history = [
        {"role": "user", "content": "у нас 5 менеджеров"},
        {"role": "assistant", "content": "понял, расскажу про бота"},
    ]
    profile = {
        "business_niche": new_field_value("медицина", confidence=0.8, extraction_type="explicit"),
        "main_pains": ["slow_response"],
    }
    prompt = build_insight_prompt("а цена какая?", history, profile)
    assert "у нас 5 менеджеров" in prompt
    assert "а цена какая?" in prompt
    assert "медицина" in prompt
    assert "slow_response" in prompt


def test_build_insight_prompt_handles_empty_inputs():
    assert build_insight_prompt("", None, None)  # no crash, still a string


# ---------------------------------------------------------------------------
# run_intelligence_turn + injected llm_extractor
# ---------------------------------------------------------------------------

def _turn(message, *, metadata=None, dialog_state=None, llm_extractor=None):
    return asyncio.run(run_intelligence_turn(
        enabled=True,
        message=message,
        chat_history=[],
        session_metadata=metadata or {},
        dialog_state=dialog_state or {},
        llm_extractor=llm_extractor,
    ))


def test_turn_merges_insights_into_profile_and_debug():
    insights = {"pain": "теряются заявки", "urgency": "high", "stage": "consideration"}

    async def extractor(*, message, chat_history, business_profile):
        return insights

    result = _turn(_STRONG_MESSAGE, llm_extractor=extractor)
    debug = result["debug"]
    assert debug["shadow_extraction_skipped_reason"] is None
    assert debug["shadow_insights"] == insights
    block = result["persist_blocks"]["business_profile"]["llm_insights"]
    assert block["pain"]["value"] == "теряются заявки"
    assert block["pain"]["confidence"] == LLM_INSIGHT_CONFIDENCE
    assert block["pain"]["extraction_type"] == "inferred"
    assert block["urgency"]["value"] == "high"
    # The heuristic top-level fields stay untouched (no heuristic urgency signal here).
    assert result["persist_blocks"]["business_profile"]["urgency"]["value"] is None


def test_turn_roleplay_never_calls_extractor():
    called = False

    async def extractor(**kwargs):
        nonlocal called
        called = True
        return {"pain": "x"}

    result = _turn(
        _STRONG_MESSAGE,
        dialog_state={"roleplay_demo_active": True},
        llm_extractor=extractor,
    )
    assert called is False
    assert result["debug"]["shadow_extraction_skipped_reason"] == "roleplay_active"
    assert "business_profile" not in result["persist_blocks"]


def test_turn_low_signal_skips_extractor():
    called = False

    async def extractor(**kwargs):
        nonlocal called
        called = True
        return {"pain": "x"}

    result = _turn("ок", llm_extractor=extractor)
    assert called is False
    assert result["debug"]["shadow_extraction_skipped_reason"] == "low_signal"


def test_turn_no_signal_reason():
    async def extractor(**kwargs):
        return None

    result = _turn(_STRONG_MESSAGE, llm_extractor=extractor)
    assert result["debug"]["shadow_extraction_skipped_reason"] == "extractor_no_signal"
    assert result["debug"]["shadow_insights"] is None
    assert "llm_insights" not in result["persist_blocks"]["business_profile"]


def test_turn_error_reason():
    async def extractor(**kwargs):
        raise RuntimeError("extractor blew up")

    result = _turn(_STRONG_MESSAGE, llm_extractor=extractor)  # must not raise
    assert result["debug"]["shadow_extraction_skipped_reason"] == "extractor_error"


def test_turn_not_configured_reason():
    result = _turn(_STRONG_MESSAGE, llm_extractor=None)
    assert result["debug"]["shadow_extraction_skipped_reason"] == "extractor_not_configured"


def test_turn_empty_insights_dict_counts_as_no_signal():
    async def extractor(**kwargs):
        return {}

    result = _turn(_STRONG_MESSAGE, llm_extractor=extractor)
    assert result["debug"]["shadow_extraction_skipped_reason"] == "extractor_no_signal"


# ---------------------------------------------------------------------------
# merge_llm_insights
# ---------------------------------------------------------------------------

def test_merge_llm_insights_never_touches_heuristic_fields():
    profile = {
        "urgency": new_field_value("low", confidence=0.9, extraction_type="explicit"),
        "main_pains": ["slow_response"],
    }
    merged = merge_llm_insights(profile, {"urgency": "high", "pain": "всё горит"})
    # Heuristic explicit field with higher confidence is untouched.
    assert merged["urgency"]["value"] == "low"
    assert merged["main_pains"] == ["slow_response"]
    # The insight lives in its own block.
    assert merged["llm_insights"]["urgency"]["value"] == "high"
    assert merged["llm_insights"]["pain"]["value"] == "всё горит"


def test_merge_llm_insights_null_never_overwrites():
    profile = merge_llm_insights({}, {"pain": "старая боль"})
    merged = merge_llm_insights(profile, {"pain": None, "urgency": "high"})
    assert merged["llm_insights"]["pain"]["value"] == "старая боль"
    assert merged["llm_insights"]["urgency"]["value"] == "high"


def test_merge_llm_insights_fresh_hypothesis_wins_with_conflict_note():
    profile = merge_llm_insights({}, {"hidden_objection": "боится цены"})
    merged = merge_llm_insights(profile, {"hidden_objection": "сравнивает с конкурентом"})
    wrapped = merged["llm_insights"]["hidden_objection"]
    assert wrapped["value"] == "сравнивает с конкурентом"
    assert wrapped["conflict"] is True
    assert wrapped["conflict_notes"]


def test_merge_llm_insights_ignores_garbage_inputs():
    assert merge_llm_insights({}, None) == {}
    assert merge_llm_insights({}, "not-a-dict") == {}
    assert merge_llm_insights(None, {"pain": "x"})["llm_insights"]["pain"]["value"] == "x"


# ---------------------------------------------------------------------------
# Golden dataset — offline contract (mocked LLM echoes the expected fields)
# ---------------------------------------------------------------------------

def test_golden_dataset_shape():
    assert len(GOLDEN_CASES) == 20
    for case in GOLDEN_CASES:
        assert case["id"] and case["message"]
        assert isinstance(case.get("history") or [], list)
        expect = case.get("expect") or {}
        assert expect, f"{case['id']}: empty expect"
        assert set(expect) <= set(INSIGHT_FIELDS), f"{case['id']}: unknown expect fields"


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_case_contract(case):
    # build_insight_prompt must not fail on any case (0-4 history messages, dicts).
    prompt = build_insight_prompt(case["message"], case.get("history") or [], None)
    assert case["message"] in prompt

    # Mocked llm_call returns a full-schema JSON built from expect; the extractor
    # must return every expected field (nulls/unknown dropped, enums normalized).
    result = asyncio.run(extract_insights(
        message=case["message"],
        chat_history=case.get("history") or [],
        business_profile=None,
        llm_call=_fake_llm(_full_payload(**case["expect"])),
    ))
    assert result is not None
    for field, expected in case["expect"].items():
        assert result.get(field) == expected, f"{case['id']}.{field}: {result.get(field)!r} != {expected!r}"
