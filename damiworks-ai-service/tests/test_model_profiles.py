"""Tests for task-specific Gemini model profiles (model routing).

Covers: config.MODEL_PROFILES defaults + env overrides, GeminiService._generate_text's
profile-based model selection and pool-order fallback, and that each live call site
(medical planner/writer/repair, DamiWorks rag_writer, router/classifier) passes the
right model_profile. Provider responses are mocked — no real Gemini calls.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from app.config import (
    BOOKING_PRIMARY,
    CHEAP_CROSS_PROVIDER_FALLBACK,
    DEFAULT_FAST_MODEL,
    ESCALATION_MODEL,
    FALLBACK_CHEAP_MODEL,
    JUDGE_MODEL,
    PREMIUM_MODEL,
    WRITER_ESCALATION,
    WRITER_FALLBACK_MODEL,
    WRITER_PRIMARY,
    GeminiApiKey,
    MODEL_PROFILES,
    Settings,
    load_model_profiles,
)
from app.gemini_service import GEMINI_ATTEMPT_TIMEOUT_MS, GeminiService, sanitize_history
from app.english_school_planner import plan_conversation_turn as plan_english_conversation_turn
from app.english_school_state import build_conversation_state as build_english_conversation_state
from app.english_school_writer import write_response as write_english_response
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
        "medical_repair", "insight_extractor", "sales_writer_escalated",
        "english_school_planner", "english_school_writer", "booking",
        "quality_eval", "default",
    ):
        assert name in MODEL_PROFILES
        assert len(MODEL_PROFILES[name]) >= 2 or name in ("quality_eval",)


def test_new_profiles_have_the_expected_defaults() -> None:
    # Cross-provider entries are part of the defaults now that ANTHROPIC/OPENAI
    # keys are configured; a keyless deployment skips them during the pool walk
    # (see test_llm_providers.py::test_unconfigured_provider_is_skipped_*).
    assert MODEL_PROFILES["insight_extractor"] == (
        DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL, CHEAP_CROSS_PROVIDER_FALLBACK,
    )
    assert MODEL_PROFILES["sales_writer_escalated"] == (
        WRITER_ESCALATION, WRITER_PRIMARY, WRITER_FALLBACK_MODEL, FALLBACK_CHEAP_MODEL,
    )
    assert MODEL_PROFILES["english_school_planner"] == (
        DEFAULT_FAST_MODEL, ESCALATION_MODEL, FALLBACK_CHEAP_MODEL,
    )
    assert MODEL_PROFILES["english_school_writer"] == (DEFAULT_FAST_MODEL, PREMIUM_MODEL)
    assert MODEL_PROFILES["booking"] == (
        BOOKING_PRIMARY, WRITER_FALLBACK_MODEL, FALLBACK_CHEAP_MODEL,
    )
    # The OpenAI nano is never a PRIMARY cheap model — only a trailing fallback.
    for name in ("router", "classifier", "insight_extractor", "memory_summary"):
        pool = MODEL_PROFILES[name]
        assert pool[0] == DEFAULT_FAST_MODEL, name
        if CHEAP_CROSS_PROVIDER_FALLBACK in pool:
            assert pool[-1] == CHEAP_CROSS_PROVIDER_FALLBACK, name


def test_quality_eval_profile_uses_the_offline_judge_model() -> None:
    assert MODEL_PROFILES["quality_eval"] == (JUDGE_MODEL, PREMIUM_MODEL)


def test_router_profile_is_fast_then_cheap_fallbacks() -> None:
    assert MODEL_PROFILES["router"] == (
        DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL, CHEAP_CROSS_PROVIDER_FALLBACK,
    )


def test_medical_planner_profile_escalates_then_falls_back() -> None:
    # The escalation model sits SECOND, not first: as a preview model it answered
    # 503 on essentially every live call, and one 503 took ~100s to return, which
    # exceeded the frontend's 55s abort budget. It is still tried when the cheap
    # default fails. See the note above MODEL_PROFILES.
    assert MODEL_PROFILES["medical_planner"] == (
        DEFAULT_FAST_MODEL, ESCALATION_MODEL, FALLBACK_CHEAP_MODEL,
    )


def test_medical_writer_profile_is_premium_first_then_lite() -> None:
    # Prospects watch the medical demo: the premium flash answers first, the
    # cheap lite is only the provider-error rescue.
    assert MODEL_PROFILES["medical_writer"] == (PREMIUM_MODEL, DEFAULT_FAST_MODEL)


def test_english_school_writer_profile_is_lite_first_then_premium() -> None:
    # Mass scenario: cheap lite leads, the premium flash is the fallback.
    assert MODEL_PROFILES["english_school_writer"] == (DEFAULT_FAST_MODEL, PREMIUM_MODEL)


def test_medical_writer_falls_back_from_premium_to_lite_on_provider_error() -> None:
    svc = _make_service()
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == PREMIUM_MODEL:
            raise RuntimeError("503 UNAVAILABLE. high demand")
        return _FakeResponse("rescued")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x", model_pool=None, model_profile="medical_writer",
        prompt="hi", system_instruction="sys", temperature=0.2, call_info=info,
    ))
    assert text == "rescued"
    assert calls == [PREMIUM_MODEL, DEFAULT_FAST_MODEL]
    assert info["selected_model"] == DEFAULT_FAST_MODEL
    assert info["fallback_used"] is True


def test_english_school_writer_falls_back_from_lite_to_premium_on_provider_error() -> None:
    svc = _make_service()
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == DEFAULT_FAST_MODEL:
            raise RuntimeError("503 UNAVAILABLE. high demand")
        return _FakeResponse("rescued")

    svc.clients["TEST"].models.generate_content = fake_generate_content

    info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x", model_pool=None, model_profile="english_school_writer",
        prompt="hi", system_instruction="sys", temperature=0.2, call_info=info,
    ))
    assert text == "rescued"
    assert calls == [DEFAULT_FAST_MODEL, PREMIUM_MODEL]
    assert info["selected_model"] == PREMIUM_MODEL
    assert info["fallback_used"] is True


def test_medical_repair_profile_can_still_reach_the_escalation_model() -> None:
    # Repair must not be limited to the exact pool that produced the bad answer:
    # it can still climb to the escalation model, which medical_writer cannot.
    assert ESCALATION_MODEL in MODEL_PROFILES["medical_repair"]
    assert ESCALATION_MODEL not in MODEL_PROFILES["medical_writer"]
    assert MODEL_PROFILES["medical_repair"] != MODEL_PROFILES["medical_writer"]


def test_sales_and_rag_writer_profiles_use_the_writer_tier() -> None:
    # WRITER tier: Claude Sonnet primary, gemini-3.5-flash cross-provider
    # fallback, cheap Gemini as the last resort. The preview escalation model
    # is deliberately NOT in the live writer pools (503 history).
    expected = (WRITER_PRIMARY, WRITER_FALLBACK_MODEL, FALLBACK_CHEAP_MODEL)
    assert MODEL_PROFILES["sales_writer"] == expected
    assert MODEL_PROFILES["rag_writer"] == expected
    assert MODEL_PROFILES["custom_demo_writer"] == expected
    assert ESCALATION_MODEL not in MODEL_PROFILES["sales_writer"]


def test_no_live_profile_starts_with_the_preview_escalation_model() -> None:
    # The regression that caused "Что-то пошло не так" on prod: a preview model
    # in front of a live-chat pool. Its 503s cost ~100s each, past the proxy's
    # 55s abort. Offline/eval profiles are exempt: nothing waits on them.
    for name, pool in MODEL_PROFILES.items():
        if name == "quality_eval":
            continue
        assert pool[0] != ESCALATION_MODEL, name


def test_load_model_profiles_env_override(monkeypatch) -> None:
    monkeypatch.setenv("MEDICAL_WRITER_MODEL_POOL", "custom-model-a,custom-model-b")
    profiles = load_model_profiles()
    assert profiles["medical_writer"] == ("custom-model-a", "custom-model-b")
    # Unset profiles keep the MODEL_PROFILES default. env_csv dedupes entries,
    # which now matters: FALLBACK_CHEAP_MODEL equals DEFAULT_FAST_MODEL, so the
    # loaded default pools collapse to the unique models only.
    assert profiles["medical_planner"] == tuple(dict.fromkeys(MODEL_PROFILES["medical_planner"]))


def test_load_model_profiles_missing_env_keeps_defaults() -> None:
    profiles = load_model_profiles()
    assert profiles["router"] == tuple(dict.fromkeys(MODEL_PROFILES["router"]))
    assert profiles["quality_eval"] == tuple(dict.fromkeys(MODEL_PROFILES["quality_eval"]))


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

    def _format_chat_prompt(self, message, history, client_facts=None, history_limit=None):
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


def test_english_school_planner_uses_english_school_planner_profile() -> None:
    gem = _RecordingGemini()
    state = build_english_conversation_state([], "хочу английский для сына")
    _run(plan_english_conversation_turn("хочу английский для сына", [], state, "kb context", gem))
    assert gem.profiles_seen == ["english_school_planner"]


def test_english_school_writer_uses_english_school_writer_profile() -> None:
    gem = _RecordingGemini()
    state = build_english_conversation_state([], "хочу английский для сына")
    planner = gem._planner_json
    _run(write_english_response("хочу английский для сына", [], state, planner, "kb context", gem))
    assert gem.profiles_seen == ["english_school_writer"]


def test_english_school_writer_repair_keeps_the_writer_profile() -> None:
    # Unlike medical there is no separate repair profile for the English demo:
    # the repair pass stays on english_school_writer.
    gem = _RecordingGemini()
    state = build_english_conversation_state([], "хочу английский для сына")
    planner = gem._planner_json
    _run(write_english_response(
        "хочу английский для сына", [], state, planner, "kb context", gem, repair="fix this",
    ))
    assert gem.profiles_seen == ["english_school_writer"]


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


# ---------------------------------------------------------------------------
# Per-attempt timeout and pool deadline.
#
# Prod incident: gemini-3-flash-preview answered 503 only after ~100 seconds.
# The model fallback then worked perfectly, but the frontend proxy had already
# aborted at 55s, so the user saw "Что-то пошло не так". A working fallback is
# worthless if it arrives after the caller has gone.
# ---------------------------------------------------------------------------

def test_every_attempt_carries_a_request_timeout() -> None:
    svc = _make_service(medical_writer=("model-a",))
    seen: list[object] = []

    def fake_generate_content(*, model, contents, config):
        seen.append(config.http_options)
        return _FakeResponse("ok")

    svc.clients["TEST"].models.generate_content = fake_generate_content
    _run(svc._generate_text(
        model="x", model_pool=None, model_profile="medical_writer",
        prompt="hi", system_instruction="sys", temperature=0.2,
    ))
    assert seen and seen[0] is not None
    assert seen[0].timeout == GEMINI_ATTEMPT_TIMEOUT_MS
    assert 0 < GEMINI_ATTEMPT_TIMEOUT_MS <= 30_000  # must stay under the 55s proxy abort


def test_pool_walk_stops_once_the_deadline_is_spent(monkeypatch) -> None:
    # A slow first candidate must not let the walk run past the deadline: the
    # remaining candidates are skipped and the caller's safe fallback answers.
    # Uses the real clock with a tiny deadline — patching time.monotonic would
    # also patch tenacity's own clock, which hangs the retry loop.
    svc = _make_service(medical_writer=("slow-a", "slow-b", "slow-c"))
    calls: list[str] = []
    monkeypatch.setattr("app.gemini_service.GEMINI_POOL_DEADLINE_SECONDS", 0.05)

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        time.sleep(0.1)              # this attempt alone outruns the deadline
        raise RuntimeError("upstream boom")  # not a 503: no tenacity retry

    svc.clients["TEST"].models.generate_content = fake_generate_content

    with pytest.raises(RuntimeError):
        _run(svc._generate_text(
            model="x", model_pool=None, model_profile="medical_writer",
            prompt="hi", system_instruction="sys", temperature=0.2,
        ))
    # The first candidate runs; the deadline is then spent, so the second and
    # third are never attempted.
    assert calls == ["slow-a"]


def test_a_slow_primary_still_lets_the_fallback_answer_in_time() -> None:
    # The prod shape: primary 503s, fallback succeeds. It must still return.
    svc = _make_service(rag_writer=("bad-primary", "good-fallback"))
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        if model == "bad-primary":
            raise RuntimeError("503 UNAVAILABLE. high demand")
        return _FakeResponse("answered")

    svc.clients["TEST"].models.generate_content = fake_generate_content
    info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x", model_pool=None, model_profile="rag_writer",
        prompt="hi", system_instruction="sys", temperature=0.2, call_info=info,
    ))
    assert text == "answered"
    assert calls == ["bad-primary", "good-fallback"]
    assert info["fallback_used"] is True
    assert "503" in str(info["fallback_reason"])


# ---------------------------------------------------------------------------
# History robustness: one malformed item must not take down the turn.
# ---------------------------------------------------------------------------

class _Broken:
    def __init__(self, role=None, content=None):
        self.role = role
        self.content = content


def test_malformed_history_items_are_skipped_not_fatal() -> None:
    history = [
        ChatHistoryMessage(role="user", content="Что за каналы"),
        _Broken(role="user", content=None),        # null content
        _Broken(role="system", content="hi"),      # unexpected role
        _Broken(role="assistant", content=123),    # non-string content
        _Broken(role="assistant", content="   "),  # whitespace only
        ChatHistoryMessage(role="assistant", content="Каналы это..."),
    ]
    clean = sanitize_history(history)
    assert [m.content for m in clean] == ["Что за каналы", "Каналы это..."]


def test_history_formatting_survives_a_malformed_item() -> None:
    history = [
        ChatHistoryMessage(role="user", content="А сколько стоит?"),
        _Broken(role="assistant", content=None),
        ChatHistoryMessage(role="assistant", content="Стоимость зависит от каналов."),
    ]
    rendered = GeminiService._format_history(history, limit=10)
    assert "А сколько стоит?" in rendered
    assert "Стоимость зависит от каналов." in rendered
    assert "None" not in rendered


def test_empty_history_renders_the_placeholder() -> None:
    assert GeminiService._format_history([], limit=10) == "No previous messages."
    assert sanitize_history(None) == []
