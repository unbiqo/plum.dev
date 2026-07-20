"""Tests for cross-provider LLM routing (app/llm_providers.py + the
GeminiService._generate_text pool walk over "provider:model" entries).

Provider SDKs are never touched over HTTP: provider clients are faked or have
their inner SDK object injected. The google side keeps using the existing
``svc.clients["TEST"].models.generate_content`` mock point.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from app.config import GeminiApiKey, MODEL_PROFILES, Settings
from app.gemini_service import GEMINI_POOL_DEADLINE_SECONDS, GeminiService
from app.llm_providers import (
    PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS,
    AnthropicProviderClient,
    GenerateRequest,
    GenerateResult,
    ModelRef,
    OpenAIProviderClient,
    ProviderError,
    ProviderRouter,
    parse_model_ref,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# parse_model_ref
# ---------------------------------------------------------------------------

def test_parse_model_ref_bare_name_means_google() -> None:
    ref = parse_model_ref("gemini-3.1-flash-lite")
    assert ref == ModelRef(provider="google", model="gemini-3.1-flash-lite")
    assert str(ref) == "google:gemini-3.1-flash-lite"


def test_parse_model_ref_anthropic_and_openai_prefixes() -> None:
    assert parse_model_ref("anthropic:claude-sonnet-5") == ModelRef(
        provider="anthropic", model="claude-sonnet-5"
    )
    assert parse_model_ref("openai:gpt-5.4-nano") == ModelRef(
        provider="openai", model="gpt-5.4-nano"
    )


def test_parse_model_ref_strips_whitespace() -> None:
    assert parse_model_ref("  anthropic:claude-opus-4-8  ") == ModelRef(
        provider="anthropic", model="claude-opus-4-8"
    )
    assert parse_model_ref("   ") == ModelRef(provider="google", model="")


def test_parse_model_ref_unknown_provider_is_returned_as_is() -> None:
    # The router simply has no client for it; the walk skips the candidate.
    ref = parse_model_ref("cohere:command-r")
    assert ref.provider == "cohere"
    assert ref.model == "command-r"


# ---------------------------------------------------------------------------
# ProviderError normalization
# ---------------------------------------------------------------------------

class _FakeHttpError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Error code: {status_code} - upstream failure")


def test_provider_error_exposes_status_and_keeps_cause() -> None:
    original = _FakeHttpError(503)
    err = ProviderError("anthropic", "claude-sonnet-5", original)
    assert err.status_code == 503
    assert err.is_server_error is True
    assert err.is_rate_limit is False
    assert "503" in str(err)  # keeps the tenacity 503-retry predicate working
    assert err.__cause__ is None  # not raised from; original kept as attribute
    assert err.original is original


def test_provider_error_marks_rate_limits() -> None:
    err = ProviderError("openai", "gpt-5.4-nano", _FakeHttpError(429))
    assert err.is_rate_limit is True
    assert err.is_server_error is False


# ---------------------------------------------------------------------------
# Provider client unit tests (SDK objects injected — no HTTP)
# ---------------------------------------------------------------------------

def test_anthropic_client_maps_text_usage_and_options() -> None:
    client = AnthropicProviderClient(api_key="fake-key")
    captured: dict = {}

    usage = SimpleNamespace(input_tokens=11, output_tokens=7, cache_read_input_tokens=3)
    response = SimpleNamespace(
        content=[SimpleNamespace(text='{"ok": true}')],
        usage=usage,
    )
    client._client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: captured.update(kw) or response)
    )

    result = client.generate(GenerateRequest(
        model="claude-sonnet-5",
        prompt="hi",
        system_instruction="sys",
        temperature=0.2,
        max_output_tokens=256,
        response_mime_type="application/json",
        response_schema={"type": "object"},
        timeout_ms=15000,
    ))

    assert result.text == '{"ok": true}'
    assert result.usage["input_tokens"] == 11
    assert result.usage["output_tokens"] == 7
    assert result.usage["total_tokens"] == 18
    assert result.usage["cached_input_tokens"] == 3
    assert result.usage["estimated"] is False
    # Prompt caching on the system block + JSON mode folded into the system text.
    system_blocks = captured["system"]
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "sys" in system_blocks[0]["text"]
    assert "JSON" in system_blocks[0]["text"]
    assert captured["max_tokens"] == 256
    assert captured["timeout"] == 15.0
    assert captured["messages"] == [{"role": "user", "content": "hi"}]


def test_anthropic_client_wraps_sdk_errors_in_provider_error() -> None:
    client = AnthropicProviderClient(api_key="fake-key")

    def boom(**kw):
        raise _FakeHttpError(429)

    client._client = SimpleNamespace(messages=SimpleNamespace(create=boom))
    with pytest.raises(ProviderError) as exc_info:
        client.generate(GenerateRequest(model="claude-sonnet-5", prompt="hi"))
    assert exc_info.value.is_rate_limit is True
    assert exc_info.value.provider == "anthropic"


def test_openai_client_maps_text_usage_and_json_mode() -> None:
    client = OpenAIProviderClient(api_key="fake-key")
    captured: dict = {}

    usage = SimpleNamespace(
        prompt_tokens=5,
        completion_tokens=2,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1),
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
        usage=usage,
    )
    client._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kw: captured.update(kw) or response)
        )
    )

    result = client.generate(GenerateRequest(
        model="gpt-5.4-nano",
        prompt="hi",
        system_instruction="sys",
        temperature=0.0,
        max_output_tokens=128,
        response_mime_type="application/json",
        timeout_ms=15000,
    ))

    assert result.text == "answer"
    assert result.usage["input_tokens"] == 5
    assert result.usage["output_tokens"] == 2
    assert result.usage["cached_input_tokens"] == 1
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["max_tokens"] == 128
    assert captured["timeout"] == 15.0
    assert captured["messages"][0] == {"role": "system", "content": "sys"}


# ---------------------------------------------------------------------------
# ProviderRouter: configured providers + cooldown
# ---------------------------------------------------------------------------

def test_router_has_clients_only_for_configured_providers() -> None:
    router = ProviderRouter()
    assert router.client_for("anthropic") is None
    assert router.client_for("openai") is None

    router = ProviderRouter(anthropic_api_key="k", openai_api_key=None)
    assert router.client_for("anthropic") is not None
    assert router.client_for("openai") is None


def test_router_cooldown_roundtrip() -> None:
    router = ProviderRouter()
    assert router.is_cooling_down("anthropic", "m") is False
    router.cool_down("anthropic", "m", 60)
    assert router.is_cooling_down("anthropic", "m") is True
    assert router.is_cooling_down("anthropic", "other") is False
    router.cool_down("anthropic", "m", 0)  # already expired
    assert router.is_cooling_down("anthropic", "m") is False


# ---------------------------------------------------------------------------
# GeminiService pool walk across providers
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.usage_metadata = None
        self.candidates = []


class _FailingProviderClient:
    """ProviderClient stand-in that always raises the given exception."""

    def __init__(self, exc: Exception):
        self.exc = exc
        self.requests: list[GenerateRequest] = []

    def generate(self, request: GenerateRequest) -> GenerateResult:
        self.requests.append(request)
        raise self.exc


class _CapturingProviderClient:
    """ProviderClient stand-in that records requests and answers successfully."""

    def __init__(self, text: str = "provider answer"):
        self.text = text
        self.requests: list[GenerateRequest] = []

    def generate(self, request: GenerateRequest) -> GenerateResult:
        self.requests.append(request)
        return GenerateResult(
            text=self.text,
            usage={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5,
                   "cached_input_tokens": 0, "thinking_tokens": 0, "estimated": False},
        )


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


def _stub_google(svc: GeminiService, text: str = "ok") -> list[str]:
    calls: list[str] = []

    def fake_generate_content(*, model, contents, config):
        calls.append(model)
        return _FakeResponse(text)

    svc.clients["TEST"].models.generate_content = fake_generate_content
    return calls


def test_cross_provider_fallback_anthropic_503_then_google(monkeypatch) -> None:
    # The key integration shape: primary provider down -> google fallback
    # answers inside the pool deadline, with the full attempt chain recorded.
    svc = _make_service(sales_writer=("anthropic:claude-sonnet-5", "gemini-3.1-flash-lite"))
    google_calls = _stub_google(svc, "recovered")
    failing = _FailingProviderClient(
        ProviderError("anthropic", "claude-sonnet-5", _FakeHttpError(503))
    )
    monkeypatch.setattr(
        svc.provider_router,
        "client_for",
        lambda provider: failing if provider == "anthropic" else None,
    )

    call_info: dict[str, object] = {}
    started = time.monotonic()
    text = _run(svc._generate_text(
        model="x",
        model_pool=None,
        model_profile="sales_writer",
        prompt="hi",
        system_instruction="sys",
        temperature=0.2,
        call_info=call_info,
    ))
    elapsed = time.monotonic() - started

    assert text == "recovered"
    assert len(failing.requests) == 1
    assert failing.requests[0].model == "claude-sonnet-5"
    assert google_calls == ["gemini-3.1-flash-lite"]
    assert call_info["fallback_used"] is True
    assert call_info["selected_model"] == "gemini-3.1-flash-lite"
    assert call_info["provider"] == "gemini"
    assert call_info["fallback_chain"] == [
        "anthropic:claude-sonnet-5",
        "google:gemini-3.1-flash-lite",
    ]
    assert elapsed < GEMINI_POOL_DEADLINE_SECONDS


def test_unconfigured_provider_is_skipped_without_an_attempt() -> None:
    # No ANTHROPIC_API_KEY configured: the candidate is skipped (debug log),
    # google answers, and the chain shows no anthropic attempt at all.
    svc = _make_service(sales_writer=("anthropic:claude-sonnet-5", "gemini-3.1-flash-lite"))
    google_calls = _stub_google(svc, "answered")

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x",
        model_pool=None,
        model_profile="sales_writer",
        prompt="hi",
        system_instruction="sys",
        temperature=0.2,
        call_info=call_info,
    ))

    assert text == "answered"
    assert google_calls == ["gemini-3.1-flash-lite"]
    assert call_info["fallback_chain"] == ["google:gemini-3.1-flash-lite"]


def test_provider_cooldown_skips_the_failing_model_next_turn(monkeypatch) -> None:
    svc = _make_service(sales_writer=("anthropic:claude-sonnet-5", "gemini-3.1-flash-lite"))
    _stub_google(svc, "ok")
    failing = _FailingProviderClient(
        ProviderError("anthropic", "claude-sonnet-5", _FakeHttpError(503))
    )
    monkeypatch.setattr(
        svc.provider_router,
        "client_for",
        lambda provider: failing if provider == "anthropic" else None,
    )

    first_info: dict[str, object] = {}
    _run(svc._generate_text(
        model="x", model_pool=None, model_profile="sales_writer",
        prompt="hi", system_instruction="sys", temperature=0.2, call_info=first_info,
    ))
    assert svc.provider_router.is_cooling_down("anthropic", "claude-sonnet-5") is True
    assert len(failing.requests) == 1

    # Next turn: the cooling-down candidate is skipped before any HTTP call.
    second_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x", model_pool=None, model_profile="sales_writer",
        prompt="hi again", system_instruction="sys", temperature=0.2, call_info=second_info,
    ))
    assert text == "ok"
    assert len(failing.requests) == 1  # no second provider attempt
    assert second_info["fallback_chain"] == ["google:gemini-3.1-flash-lite"]


def test_provider_rate_limit_cools_down_longer(monkeypatch) -> None:
    svc = _make_service(sales_writer=("openai:gpt-5.4-nano", "gemini-3.1-flash-lite"))
    _stub_google(svc, "ok")
    failing = _FailingProviderClient(
        ProviderError("openai", "gpt-5.4-nano", _FakeHttpError(429))
    )
    monkeypatch.setattr(
        svc.provider_router,
        "client_for",
        lambda provider: failing if provider == "openai" else None,
    )

    _run(svc._generate_text(
        model="x", model_pool=None, model_profile="sales_writer",
        prompt="hi", system_instruction="sys", temperature=0.2,
    ))
    assert svc.provider_router.is_cooling_down("openai", "gpt-5.4-nano") is True
    # 429 uses the longer cooldown (10 min), not the 5-min failure one.
    assert svc.provider_router._cooldowns[("openai", "gpt-5.4-nano")] > (
        time.monotonic() + PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS - 30
    )


def test_fast_failing_provider_does_not_burn_the_pool_deadline(monkeypatch) -> None:
    # Deadline analog of test_pool_walk_stops_once_the_deadline_is_spent, but
    # with the first candidate living on another provider: its failure is fast,
    # so the google candidate still answers well within the deadline.
    svc = _make_service(rag_writer=("anthropic:claude-sonnet-5", "gemini-3.1-flash-lite"))
    google_calls = _stub_google(svc, "in time")
    failing = _FailingProviderClient(
        ProviderError("anthropic", "claude-sonnet-5", _FakeHttpError(503))
    )
    monkeypatch.setattr(
        svc.provider_router,
        "client_for",
        lambda provider: failing if provider == "anthropic" else None,
    )

    started = time.monotonic()
    text = _run(svc._generate_text(
        model="x", model_pool=None, model_profile="rag_writer",
        prompt="hi", system_instruction="sys", temperature=0.2,
    ))
    elapsed = time.monotonic() - started

    assert text == "in time"
    assert google_calls == ["gemini-3.1-flash-lite"]
    assert elapsed < GEMINI_POOL_DEADLINE_SECONDS


# ---------------------------------------------------------------------------
# Default pools wired to the configured providers (writer/booking/cheap)
# ---------------------------------------------------------------------------

def test_default_sales_writer_pool_goes_to_anthropic(monkeypatch) -> None:
    # WRITER tier wiring: with the default MODEL_PROFILES the first sales_writer
    # attempt lands on the anthropic branch (claude-sonnet-5), no google call.
    svc = _make_service()
    google_calls = _stub_google(svc, "google should not be called")
    anthropic = _CapturingProviderClient("sonnet answer")
    monkeypatch.setattr(
        svc.provider_router,
        "client_for",
        lambda provider: anthropic if provider == "anthropic" else None,
    )

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x",
        model_pool=None,
        model_profile="sales_writer",
        prompt="hi",
        system_instruction="sys",
        temperature=0.85,
        call_info=call_info,
    ))

    assert text == "sonnet answer"
    assert [r.model for r in anthropic.requests] == ["claude-sonnet-5"]
    assert anthropic.requests[0].temperature == 0.85
    assert google_calls == []
    assert call_info["provider"] == "anthropic"
    assert call_info["selected_model"] == "claude-sonnet-5"
    assert call_info["fallback_used"] is False
    assert call_info["fallback_chain"] == ["anthropic:claude-sonnet-5"]


def test_default_booking_pool_goes_to_openai(monkeypatch) -> None:
    # Booking/structured-outputs wiring: gpt-5.6-luna first on the openai branch.
    svc = _make_service()
    google_calls = _stub_google(svc, "google should not be called")
    openai_client = _CapturingProviderClient('{"slot": "завтра 10:00"}')
    monkeypatch.setattr(
        svc.provider_router,
        "client_for",
        lambda provider: openai_client if provider == "openai" else None,
    )

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x",
        model_pool=None,
        model_profile="booking",
        prompt="hi",
        system_instruction="sys",
        temperature=0.0,
        response_mime_type="application/json",
        call_info=call_info,
    ))

    assert text == '{"slot": "завтра 10:00"}'
    assert [r.model for r in openai_client.requests] == ["gpt-5.6-luna"]
    assert openai_client.requests[0].response_mime_type == "application/json"
    assert google_calls == []
    assert call_info["provider"] == "openai"
    assert call_info["selected_model"] == "gpt-5.6-luna"
    assert call_info["fallback_used"] is False


def test_missing_openai_key_skips_to_google_in_booking_pool() -> None:
    # Robustness: booking pool without OPENAI_API_KEY — the openai candidate is
    # skipped without an attempt and the google fallback answers.
    svc = _make_service()
    google_calls = _stub_google(svc, "recovered by google")

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x",
        model_pool=None,
        model_profile="booking",
        prompt="hi",
        system_instruction="sys",
        temperature=0.0,
        call_info=call_info,
    ))

    assert text == "recovered by google"
    assert google_calls == ["gemini-3.5-flash"]
    assert call_info["provider"] == "gemini"
    assert call_info["fallback_chain"] == ["google:gemini-3.5-flash"]


def test_missing_anthropic_key_skips_to_google_in_writer_pool() -> None:
    # Robustness: writer pool without ANTHROPIC_API_KEY — same skip semantics.
    svc = _make_service()
    google_calls = _stub_google(svc, "recovered by google")

    call_info: dict[str, object] = {}
    text = _run(svc._generate_text(
        model="x",
        model_pool=None,
        model_profile="sales_writer",
        prompt="hi",
        system_instruction="sys",
        temperature=0.85,
        call_info=call_info,
    ))

    assert text == "recovered by google"
    assert google_calls == ["gemini-3.5-flash"]
    assert call_info["provider"] == "gemini"
    assert call_info["fallback_chain"] == ["google:gemini-3.5-flash"]
