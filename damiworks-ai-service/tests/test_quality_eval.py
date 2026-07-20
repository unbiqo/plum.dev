"""Tests for the offline quality judge (app/quality_eval.py) and the nightly
sample helpers (scripts/nightly_quality_eval.py). The judge LLM is mocked —
no real Gemini calls."""

from __future__ import annotations

import asyncio
import json

from app.quality_eval import (
    EVAL_RUBRIC_KEYS,
    build_judge_prompt,
    evaluate_conversation,
    mean_scores,
    parse_eval_result,
)


def _run(coro):
    return asyncio.run(coro)


def _valid_payload(**overrides) -> dict:
    payload = {
        "naturalness": 5,
        "pain_discovery": 4,
        "funnel_progression": 4,
        "rag_factual_accuracy": 5,
        "guardrail_compliance": 5,
        "verdict": "pass",
        "recommendations": "Добавить правило: один вопрос за ответ.",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# parse_eval_result
# ---------------------------------------------------------------------------

def test_parse_valid_result() -> None:
    result = parse_eval_result(json.dumps(_valid_payload()))
    assert result is not None
    assert result["scores"]["naturalness"] == 5
    assert set(result["scores"]) == set(EVAL_RUBRIC_KEYS)
    assert result["verdict"] == "pass"
    assert result["recommendations"]


def test_parse_rejects_non_json() -> None:
    assert parse_eval_result("not json at all") is None
    assert parse_eval_result("") is None
    assert parse_eval_result("[1,2,3]") is None


def test_parse_rejects_score_out_of_range() -> None:
    assert parse_eval_result(json.dumps(_valid_payload(naturalness=7))) is None
    assert parse_eval_result(json.dumps(_valid_payload(naturalness=0))) is None
    assert parse_eval_result(json.dumps(_valid_payload(naturalness="high"))) is None


def test_parse_rejects_missing_score() -> None:
    payload = _valid_payload()
    del payload["guardrail_compliance"]
    assert parse_eval_result(json.dumps(payload)) is None


def test_parse_rejects_bad_verdict() -> None:
    assert parse_eval_result(json.dumps(_valid_payload(verdict="great"))) is None


# ---------------------------------------------------------------------------
# build_judge_prompt
# ---------------------------------------------------------------------------

def test_build_judge_prompt_renders_transcript() -> None:
    prompt = build_judge_prompt(
        transcript=[
            {"role": "user", "content": "Сколько стоит?"},
            {"role": "assistant", "content": "Зависит от объёма. А какой у вас канал?"},
            {"role": "system", "content": "игнорируется"},
            {"role": "user", "content": "   "},
        ],
        instance_id="damiworks_site",
    )
    assert "Клиент: Сколько стоит?" in prompt
    assert "Ассистент:" in prompt
    assert "игнорируется" not in prompt
    assert "damiworks_site" in prompt


# ---------------------------------------------------------------------------
# evaluate_conversation (mocked gemini)
# ---------------------------------------------------------------------------

class _FakeSettings:
    router_model = "fake-model"


class _FakeGemini:
    def __init__(self, text: str | Exception):
        self.settings = _FakeSettings()
        self._text = text
        self.calls: list[dict] = []

    async def _generate_text(self, **kw):
        self.calls.append(kw)
        if isinstance(self._text, Exception):
            raise self._text
        if "call_info" in kw and isinstance(kw["call_info"], dict):
            kw["call_info"]["selected_model"] = "gemini-3.1-pro"
        return self._text


def test_evaluate_conversation_uses_quality_eval_profile() -> None:
    gemini = _FakeGemini(json.dumps(_valid_payload()))
    result = _run(evaluate_conversation(
        gemini,
        transcript=[{"role": "user", "content": "Привет"}],
        instance_id="damiworks_site",
    ))
    assert result is not None
    assert result["judge_model"] == "gemini-3.1-pro"
    assert gemini.calls[0]["model_profile"] == "quality_eval"
    assert gemini.calls[0]["temperature"] == 0.1


def test_evaluate_conversation_returns_none_on_llm_error() -> None:
    gemini = _FakeGemini(RuntimeError("judge down"))
    assert _run(evaluate_conversation(
        gemini, transcript=[{"role": "user", "content": "x"}], instance_id="i",
    )) is None


def test_evaluate_conversation_returns_none_on_bad_json() -> None:
    gemini = _FakeGemini("судья сказал что всё хорошо")
    assert _run(evaluate_conversation(
        gemini, transcript=[{"role": "user", "content": "x"}], instance_id="i",
    )) is None


# ---------------------------------------------------------------------------
# mean_scores
# ---------------------------------------------------------------------------

def test_mean_scores() -> None:
    results = [
        {"scores": dict.fromkeys(EVAL_RUBRIC_KEYS, 4), "verdict": "pass"},
        {"scores": dict.fromkeys(EVAL_RUBRIC_KEYS, 2), "verdict": "fail"},
    ]
    means = mean_scores(results)
    assert means["naturalness"] == 3.0
    assert set(means) == set(EVAL_RUBRIC_KEYS)


# ---------------------------------------------------------------------------
# Weekly-run sampling/window helpers
# ---------------------------------------------------------------------------

def test_weekly_default_sample_rate_takes_every_conversation() -> None:
    # The weekly run judges 100% of dialogs (volume is small, no sampling).
    from scripts.nightly_quality_eval import _sample_conversations
    from datetime import date

    rows = [{"instance_id": "i", "chat_id": f"c{n}"} for n in range(37)]
    assert _sample_conversations(rows, 1.0, 200, date(2026, 7, 19)) == rows


def test_weekly_window_spans_seven_days_ending_on_the_given_day() -> None:
    from scripts.nightly_quality_eval import _window
    from datetime import date

    date_from, date_to = _window(date(2026, 7, 19), 7)
    assert date_from == "2026-07-13T00:00:00+00:00"  # 7 full days: 13..19
    assert date_to == "2026-07-20T00:00:00+00:00"    # exclusive end
    one_from, one_to = _window(date(2026, 7, 19), 1)
    assert one_from == "2026-07-19T00:00:00+00:00"
    assert one_to == date_to


def test_nightly_sampling_is_deterministic_and_bounded() -> None:
    from scripts.nightly_quality_eval import _sample_conversations
    from datetime import date

    rows = [{"instance_id": "i", "chat_id": f"c{n}"} for n in range(100)]
    day = date(2026, 7, 17)
    first = _sample_conversations(rows, 0.2, 200, day)
    second = _sample_conversations(rows, 0.2, 200, day)
    assert first == second  # same day -> same sample
    assert 0 < len(first) < len(rows)
    capped = _sample_conversations(rows, 1.0, 10, day)
    assert len(capped) == 10
    empty = _sample_conversations([], 0.2, 200, day)
    assert empty == []


def test_nightly_transcript_extraction() -> None:
    from scripts.nightly_quality_eval import _transcript_of

    detail = {
        "messages": [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуйте!"},
            {"role": "system", "content": "skip"},
            {"role": "user", "content": "  "},
        ]
    }
    transcript = _transcript_of(detail)
    assert transcript == [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуйте!"},
    ]
