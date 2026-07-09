"""Tests for task-specific Gemini model profiles (model routing).

Covers: config.MODEL_PROFILES defaults + env overrides, GeminiService._generate_text's
profile-based model selection and pool-order fallback, and that each live call site
(medical planner/writer/repair, DamiWorks rag_writer, router/classifier) passes the
right model_profile. Provider responses are mocked — no real Gemini calls.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.config import (
    DEFAULT_FAST_MODEL,
    ESCALATION_MODEL,
    FALLBACK_CHEAP_MODEL,
    GeminiApiKey,
    MODEL_PROFILES,
    Settings,
    load_model_profiles,
)
from app.gemini_service import GeminiService
from app.medical_center_planner import plan_conversation_turn
from app.medical_center_state import build_conversation_state
from app.medical_center_writer import write_response
from app.schemas import ChatHistoryMessage


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Config: profile defaults + env overrides + unknown-profile fallback
# ---------------------------------------------------------------------------

def test_model_profiles_defaults_exist_for_every_named_task_type() -> None:
    for name in (
        "router", "classifier", "sales_writer", "rag_writer", "custom_demo_writer",
        "attachment_extraction", "memory_summary", "medical_planner", "medical_writer",
        "medical_repair", "quality_eval", "default",
    ):
        assert name in MODEL_PROFILES
        assert len(MODEL_PROFILES[name]) >= 2 or name in ("quality_eval",)


def test_router_profile_is_fast_then_cheap_fallback() -> None:
    assert MODEL_PROFILES["router"] == (DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL)


def test_medical_planner_profile_escalates_then_falls_back() -> None:
    assert MODEL_PROFILES["medical_planner"] == (
        ESCALATION_MODEL, DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL,
    )


def test_medical_writer_profile_is_fast_then_cheap_fallback() -> None:
    assert MODEL_PROFILES["medical_writer"] == (DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL)


def test_medical_repair_profile_escalates_above_medical_writer() -> None:
    # Repair must not reuse the exact same weak-primary pool that produced the
    # bad answer in the first place.
    assert MODEL_PROFILES["medical_repair"][0] == ESCALATION_MODEL
    assert MODEL_PROFILES["medical_repair"] != MODEL_PROFILES["medical_writer"]


def test_sales_and_rag_writer_profiles_escalate_then_fall_back() -> None:
    expected = (ESCALATION_MODEL, DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL)
    assert MODEL_PROFILES["sales_writer"] == expected
    assert MODEL_PROFILES["rag_writer"] == expected


def test_load_model_profiles_env_override(monkeypatch) -> None:
    monkeypatch.setenv("MEDICAL_WRITER_MODEL_POOL", "custom-model-a,custom-model-b")
    profiles = load_model_profiles()
    assert profiles["medical_writer"] == ("custom-model-a", "custom-model-b")
    # Unset profiles keep the MODEL_PROFILES default.
    assert profiles["medical_planner"] == MODEL_PROFILES["medical_planner"]


def test_load_model_profiles_missing_env_keeps_defaults() -> None:
    profiles = load_model_profiles()
    assert profiles["router"] == MODEL_PROFILES["router"]
    assert profiles["quality_eval"] == MODEL_PROFILES["quality_eval"]


# ---------------------------------------------------------------------------
# GeminiService._generate_text: profile resolution + pool-order fallback
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.usage_metadata = None
        self.candidates = []


def _make_service(**profile_overrides) -> GeminiService:
    profiles = dict(MODEL_PROFILES)
    profiles.update(profile_overrides)
    settings = Settings(
        gemini_api_keys=(GeminiApiKey("TEST", "fake-key"),),
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="fake",
        model_profiles=profiles,
    )
    return GeminiService(settings)


def test_generate_text_uses_model_profile_pool_and_records_call_info() -> None:
    svc = _make_service(medical_writer=("model-a", "model-b"))
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        return _FakeResponse("hello")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="unused-legacy-model",
        model_pool=("unused-legacy-pool-model",),
        model_profile="medical_writer",
        prompt="hi",
        system_instruction="sys",
        temperature=0.2,
        call_info=call_info,
    ))
    assert text == "hello"
    assert calls == ["model-a"]  # first candidate in the profile pool, not the legacy args
    assert call_info["model_profile"] == "medical_writer"
    assert call_info["selected_model"] == "model-a"
    assert call_info["fallback_used"] is False


def test_generate_text_falls_back_to_next_model_in_pool_on_provider_error() -> None:
    svc = _make_service(medical_writer=("bad-model", "good-model"))
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == "bad-model":
            raise RuntimeError("503 model overloaded")
        return _FakeResponse("recovered")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x", model_pool=None, model_profile="medical_writer",
        prompt="hi", system_instruction="sys", temperature=0.2,
        call_info=call_info,
    ))
    assert text == "recovered"
    assert calls == ["bad-model", "good-model"]
    assert call_info["selected_model"] == "good-model"
    assert call_info["fallback_used"] is True


def test_generate_text_unknown_profile_falls_back_to_legacy_model_pool() -> None:
    svc = _make_service()
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        return _FakeResponse("ok")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    call_info: dict[str, object] = {}
    _run(svc._generate_text(
        model="legacy-model", model_pool=("legacy-model", "legacy-fallback"),
        model_profile="totally_unknown_profile_name",
        prompt="hi", system_instruction="sys", temperature=0.2,
        call_info=call_info,
    ))
    assert calls == ["legacy-model"]
    assert call_info["model_pool"] == ("legacy-model", "legacy-fallback")


def test_generate_text_without_model_profile_keeps_legacy_behavior() -> None:
    # Existing call sites that never pass model_profile must be unaffected.
    svc = _make_service()
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        return _FakeResponse("ok")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    text = _run(svc._generate_text(
        model="m1", model_pool=("m1", "m2"),
        prompt="hi", system_instruction="sys", temperature=0.2,
    ))
    assert text == "ok"
    assert calls == ["m1"]


def test_generate_text_all_candidates_exhausted_raises_and_records_call_info() -> None:
    svc = _make_service(medical_writer=("bad-a", "bad-b"))

    def fake_generate_content(*, model, contents, config):
        raise RuntimeError(f"{model} is down")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    call_info: dict[str, object] = {}
    with pytest.raises(RuntimeError):
        _run(svc._generate_text(
            model="x", model_pool=None, model_profile="medical_writer",
            prompt="hi", system_instruction="sys", temperature=0.2,
            call_info=call_info,
        ))
    assert call_info["fallback_used"] is True
    assert call_info["selected_model"] is None


# ---------------------------------------------------------------------------
# Live call sites pass the right model_profile
# ---------------------------------------------------------------------------

class _RecordingGemini:
    """Records the model_profile passed to _generate_text; returns queued output."""

    class _Settings:
        general_model = "fake-model"
        general_model_pool = ("fake-model",)
        rag_model = "fake-model"
        rag_model_pool = ("fake-model",)
        router_model = "fake-model"
        router_model_pool = ("fake-model",)

    def __init__(self, planner_json: dict | None = None, writer_text: str = "ok"):
        self.settings = self._Settings()
        self._planner_json = planner_json or {
            "current_intent": "answer_question", "intent_priority": "high",
            "should_pause_qualification": True, "user_frustration": False,
            "correction": False, "question_to_answer": "q", "response_goal": "g",
            "must_mention": [], "must_not_repeat": [], "recommended_next_step": "none",
            "do_not_ask": [], "handoff_recommended": False, "reason": "test", "slots": {},
        }
        self._writer_text = writer_text
        self.profiles_seen: list[str | None] = []

    async def _generate_text(self, **kw):
        self.profiles_seen.append(kw.get("model_profile"))
        if kw.get("response_mime_type") == "application/json":
            return json.dumps(self._planner_json)
        return self._writer_text

    def _format_chat_prompt(self, message, history, client_facts=None):
        return f"USER: {message}"


def test_medical_planner_uses_medical_planner_profile() -> None:
    gem = _RecordingGemini()
    state = build_conversation_state([], "болит ухо")
    _run(plan_conversation_turn("болит ухо", [], state, "core context", gem))
    assert gem.profiles_seen == ["medical_planner"]


def test_medical_writer_uses_medical_writer_profile_normally() -> None:
    gem = _RecordingGemini()
    state = build_conversation_state([], "болит ухо")
    planner = gem._planner_json
    _run(write_response("болит ухо", [], state, planner, "kb context", gem))
    assert gem.profiles_seen == ["medical_writer"]


def test_medical_writer_uses_medical_repair_profile_on_repair_pass() -> None:
    gem = _RecordingGemini()
    state = build_conversation_state([], "болит ухо")
    planner = gem._planner_json
    _run(write_response(
        "болит ухо", [], state, planner, "kb context", gem, repair="fix this",
    ))
    assert gem.profiles_seen == ["medical_repair"]


def test_answer_with_route_json_uses_rag_writer_profile() -> None:
    svc = _make_service()

    async def fake_generate_text(**kw):
        assert kw.get("model_profile") == "rag_writer"
        return json.dumps({
            "predicted_route": "GENERAL",
            "text_response": "hello",
            "json_valid": True,
        })

    svc._generate_text = fake_generate_text
    result = _run(svc.answer_with_route_json(
        message="hi", chat_history=[], rag_context="", commercial_context="",
        memory_context="", response_instruction="", system_prompt_addon="",
        final_system_prompt="", router_system_prompt="", client_facts={},
    ))
    assert result.get("model_info", {}).get("model_profile") != "sales_writer"


def test_classify_sales_stage_transition_uses_classifier_profile() -> None:
    svc = _make_service()
    seen: list[str | None] = []

    async def fake_generate_text(**kw):
        seen.append(kw.get("model_profile"))
        return json.dumps({"stage": "none", "commercial_intent": False, "checkout_intent": False})

    svc._generate_text = fake_generate_text
    _run(svc.classify_sales_stage_transition("привет", []))
    assert seen == ["classifier"]


def test_classify_content_followup_uses_classifier_profile() -> None:
    svc = _make_service()
    seen: list[str | None] = []

    async def fake_generate_text(**kw):
        seen.append(kw.get("model_profile"))
        return "none"

    svc._generate_text = fake_generate_text
    history = [ChatHistoryMessage(role="assistant", content="Уточните ваш город?")]
    _run(svc.classify_content_followup("да", history))
    assert seen == ["classifier"]
