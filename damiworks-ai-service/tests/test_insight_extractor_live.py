"""Opt-in LIVE accuracy run of the insight extractor over the golden dataset.

Calls the REAL Gemini API on the ``insight_extractor`` profile for all 20 cases in
``tests/golden/insight_extractor_cases.yaml`` and asserts field-level accuracy >= 0.8.

Matching rule (documented): enum fields (``urgency``, ``stage``) must match exactly;
free-text fields (``pain``, ``budget_signals``, ``hidden_objection``,
``client_intent_vector``) use a fuzzy RU match — casefolded substring containment in
either direction, or at least half of the expected content words (length >= 4)
present in the actual string.

Run locally:
    RUN_LIVE_EVALS=1 python -m pytest tests/test_insight_extractor_live.py -q
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import pytest
import yaml

from app.sales_intelligence.extractor import INSIGHT_SCHEMA, extract_insights

pytestmark = pytest.mark.live

if os.getenv("RUN_LIVE_EVALS") != "1":
    pytest.skip("live evals disabled (set RUN_LIVE_EVALS=1)", allow_module_level=True)

GOLDEN_PATH = Path(__file__).parent / "golden" / "insight_extractor_cases.yaml"

with GOLDEN_PATH.open(encoding="utf-8") as _fh:
    GOLDEN_CASES = yaml.safe_load(_fh)

_ENUM_FIELDS = ("urgency", "stage")
_ACCURACY_THRESHOLD = 0.8


@pytest.fixture(scope="module")
def gemini():
    from app.config import get_settings
    from app.gemini_service import GeminiService

    settings = get_settings()
    if not getattr(settings, "gemini_api_keys", None):
        pytest.skip("no Gemini API keys configured")
    return GeminiService(settings)


def _content_words(text: str) -> list[str]:
    return [w for w in re.split(r"[^0-9a-zA-Zа-яё]+", text.casefold()) if len(w) >= 4]


def _string_match(expected: str, actual: str) -> bool:
    """Fuzzy RU match for free-text fields (see module docstring for the rule)."""
    norm_e = " ".join(_content_words(expected))
    norm_a = " ".join(_content_words(actual))
    if not norm_e or not norm_a:
        return False
    if norm_e in norm_a or norm_a in norm_e:
        return True
    expected_words = set(norm_e.split())
    hits = sum(1 for w in expected_words if w in norm_a)
    return hits >= max(1, len(expected_words) / 2)


def test_golden_live_field_accuracy(gemini):
    settings = gemini.settings

    async def llm_call(*, prompt, system_instruction):
        return await gemini._generate_text(
            model=settings.router_model,
            model_pool=None,
            model_profile="insight_extractor",
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.1,
            max_output_tokens=400,
            response_mime_type="application/json",
            response_schema=INSIGHT_SCHEMA,
        )

    total = 0
    matched = 0
    misses: list[str] = []
    for case in GOLDEN_CASES:
        result = asyncio.run(extract_insights(
            message=case["message"],
            chat_history=case.get("history") or [],
            business_profile=None,
            llm_call=llm_call,
        ))
        for field, expected in (case.get("expect") or {}).items():
            total += 1
            actual = (result or {}).get(field)
            if field in _ENUM_FIELDS:
                ok = actual == expected
            else:
                ok = isinstance(actual, str) and _string_match(str(expected), actual)
            if ok:
                matched += 1
            else:
                misses.append(f"{case['id']}.{field}: expected {expected!r}, got {actual!r}")

    accuracy = matched / total if total else 0.0
    assert accuracy >= _ACCURACY_THRESHOLD, (
        f"field accuracy {accuracy:.2%} < {_ACCURACY_THRESHOLD:.0%} "
        f"({matched}/{total}); misses:\n" + "\n".join(misses)
    )
