from __future__ import annotations

import asyncio

from app.config import GeminiApiKey, MODEL_PROFILES, Settings
from app.gemini_service import GeminiService
from app.llm_usage import (
    aggregate_llm_calls,
    begin_llm_usage_context,
    calculate_llm_cost,
    current_llm_calls,
    end_llm_usage_context,
    usage_from_response,
)


def _run(coro):
    return asyncio.run(coro)


class _Usage:
    prompt_token_count = 100
    candidates_token_count = 30
    total_token_count = 130
    cached_content_token_count = 5
    thoughts_token_count = 7


class _Response:
    def __init__(self, text: str = "ok", usage_metadata: object | None = None):
        self.text = text
        self.usage_metadata = usage_metadata
        self.candidates = []


def _make_service() -> GeminiService:
    settings = Settings(
        gemini_api_keys=(GeminiApiKey("TEST", "fake-key"),),
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="fake",
        model_profiles={**MODEL_PROFILES, "medical_writer": ("gemini-3.1-flash-lite", "gemini-2.5-flash-lite")},
    )
    return GeminiService(settings)


def test_cost_calculation_known_models() -> None:
    assert calculate_llm_cost("gemini-3.1-flash-lite", 1_000_000, 1_000_000)["total_cost_usd"] == 1.75
    assert calculate_llm_cost("gemini-2.5-flash-lite", 1_000_000, 1_000_000)["total_cost_usd"] == 0.5
    assert calculate_llm_cost("gemini-3-flash-preview", 1_000_000, 1_000_000)["total_cost_usd"] == 3.5


def test_cost_calculation_unknown_model_marks_missing_pricing() -> None:
    result = calculate_llm_cost("unknown-model", 100, 50)
    assert result["pricing_missing"] is True
    assert result["total_cost_usd"] is None


def test_usage_metadata_parsing_real_and_estimated() -> None:
    real = usage_from_response(_Response(usage_metadata=_Usage()), estimated_input_tokens=10, estimated_output_tokens=3)
    assert real["input_tokens"] == 100
    assert real["output_tokens"] == 30
    assert real["cached_input_tokens"] == 5
    assert real["thinking_tokens"] == 7
    assert real["estimated"] is False

    estimated = usage_from_response(_Response(usage_metadata=None), estimated_input_tokens=10, estimated_output_tokens=3)
    assert estimated["input_tokens"] == 10
    assert estimated["output_tokens"] == 3
    assert estimated["estimated"] is True


def test_generate_text_records_tokens_cost_and_no_prompt() -> None:
    svc = _make_service()

    def fake_generate_content(*, model, contents, config):
        return _Response("hello", usage_metadata=_Usage())

    svc.clients["TEST"].models.generate_content = fake_generate_content
    token = begin_llm_usage_context(instance_id="damiworks_site", chat_id="chat-1", message_id="ai-1")
    try:
        call_info: dict[str, object] = {}
        text = _run(svc._generate_text(
            model="unused",
            model_pool=None,
            model_profile="medical_writer",
            prompt="SECRET PROMPT",
            system_instruction="sys",
            temperature=0.2,
            call_info=call_info,
        ))
        calls = current_llm_calls()
    finally:
        end_llm_usage_context(token)

    assert text == "hello"
    assert call_info["selected_model"] == "gemini-3.1-flash-lite"
    assert call_info["input_tokens"] == 100
    assert call_info["output_tokens"] == 30
    assert call_info["total_cost_usd"] is not None
    assert calls and calls[0]["model_profile"] == "medical_writer"
    assert "SECRET PROMPT" not in str(calls[0])


def test_generate_text_fallback_logs_selected_fallback_model() -> None:
    svc = _make_service()

    def fake_generate_content(*, model, contents, config):
        if model == "gemini-3.1-flash-lite":
            raise RuntimeError("503 overloaded")
        return _Response("fallback", usage_metadata=_Usage())

    svc.clients["TEST"].models.generate_content = fake_generate_content
    token = begin_llm_usage_context(instance_id="damiworks_site", chat_id="chat-2")
    try:
        call_info: dict[str, object] = {}
        text = _run(svc._generate_text(
            model="unused",
            model_pool=None,
            model_profile="medical_writer",
            prompt="hi",
            system_instruction="sys",
            temperature=0.2,
            call_info=call_info,
        ))
        calls = current_llm_calls()
    finally:
        end_llm_usage_context(token)

    assert text == "fallback"
    assert call_info["selected_model"] == "gemini-2.5-flash-lite"
    assert call_info["fallback_used"] is True
    assert calls[0]["selected_model"] == "gemini-2.5-flash-lite"
    assert calls[0]["fallback_used"] is True


def test_conversation_aggregation_by_model_and_task() -> None:
    calls = [
        {
            "selected_model": "gemini-3.1-flash-lite",
            "task_type": "medical_writer",
            "model_profile": "medical_writer",
            "input_tokens": 100,
            "output_tokens": 30,
            "total_tokens": 130,
            "total_cost_usd": 0.00007,
            "estimated": False,
            "pricing_missing": False,
            "fallback_used": False,
            "latency_ms": 100,
        },
        {
            "selected_model": "gemini-3-flash-preview",
            "task_type": "medical_planner",
            "model_profile": "medical_planner",
            "input_tokens": 200,
            "output_tokens": 20,
            "total_tokens": 220,
            "total_cost_usd": 0.00016,
            "estimated": True,
            "pricing_missing": False,
            "fallback_used": True,
            "latency_ms": 250,
        },
    ]
    result = aggregate_llm_calls(calls)
    assert result["total_input_tokens"] == 300
    assert result["total_output_tokens"] == 50
    assert result["fallback_count"] == 1
    assert result["has_estimated_usage"] is True
    assert len(result["by_model"]) == 2
    assert len(result["by_task"]) == 2
