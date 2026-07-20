"""Cross-provider LLM routing primitives.

Model pools (config.MODEL_PROFILES / *_MODEL_POOL env vars) may now mix
providers using the ``provider:model`` syntax, e.g.
``anthropic:claude-sonnet-5`` or ``openai:gpt-5.4-nano``. A bare model name
without a prefix keeps the legacy meaning of ``google`` (Gemini), so every
existing pool stays valid.

This module holds the non-Google side of that routing:
- ``ModelRef`` / ``parse_model_ref`` — pool entry parsing.
- ``ProviderClient`` implementations for Anthropic and OpenAI, normalizing
  text + token usage into the llm_usage dict shape.
- ``ProviderError`` — normalized provider failure so the caller can tell a
  rate limit (429) from a server error (5xx) without SDK-specific imports.
- ``ProviderRouter`` — one client per configured provider (created only when
  the API key exists) plus a per-(provider, model) cooldown, the
  cross-provider equivalent of gemini_quota's failure cooldown.

Google stays on the existing path inside GeminiService (quota manager,
per-key walk); this module deliberately does not wrap it.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol


logger = logging.getLogger(__name__)

GOOGLE_PROVIDER = "google"
KNOWN_PROVIDERS = (GOOGLE_PROVIDER, "anthropic", "openai")

# Mirrors FAILURE_COOLDOWN_SECONDS in gemini_quota: after a 5xx/timeout the
# (provider, model) pair is skipped for 5 minutes. Rate limits cool down
# longer — a 429 usually means the account/rate window needs more time.
PROVIDER_FAILURE_COOLDOWN_SECONDS = 5 * 60
PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS = 10 * 60


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model: str
    timeout_ms: int | None = None
    max_retries: int | None = None

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_model_ref(raw: str) -> ModelRef:
    """Parse a pool entry into a ModelRef.

    ``"anthropic:claude-sonnet-5"`` -> ModelRef(provider="anthropic", ...).
    A bare name (``"gemini-3.1-flash-lite"``) means provider="google" for
    backwards compatibility with every existing pool. An unknown provider
    prefix is returned as-is — the router simply has no client for it and the
    candidate is skipped by the caller.
    """
    text = (raw or "").strip()
    if ":" in text:
        provider, _, model = text.partition(":")
        provider = provider.strip().lower()
        model = model.strip()
        if provider and model:
            return ModelRef(provider=provider, model=model)
    return ModelRef(provider=GOOGLE_PROVIDER, model=text)


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    prompt: str
    system_instruction: str = ""
    temperature: float = 0.0
    max_output_tokens: int | None = None
    response_mime_type: str | None = None
    response_schema: dict[object, object] | None = None
    timeout_ms: int | None = None


@dataclass
class GenerateResult:
    text: str
    # Usage in the llm_usage dict shape: input_tokens / output_tokens /
    # total_tokens / cached_input_tokens / thinking_tokens / estimated.
    usage: dict[str, Any]
    raw: Any | None = None


class ProviderClient(Protocol):
    """Synchronous provider client; invoked inside asyncio.to_thread."""

    def generate(self, request: GenerateRequest) -> GenerateResult:
        ...


class ProviderError(RuntimeError):
    """Normalized non-Google provider failure.

    Never swallows the original exception (kept as __cause__); exposes the
    HTTP-ish status so the walk can pick the right cooldown, and keeps the
    status in the message text so the existing 503-retry predicate in
    gemini_service keeps working for provider failures too.
    """

    def __init__(self, provider: str, model: str, original: BaseException) -> None:
        self.provider = provider
        self.model = model
        self.original = original
        self.status_code = self._extract_status_code(original)
        super().__init__(f"{provider} error for model {model}: {original}")

    @staticmethod
    def _extract_status_code(exc: BaseException) -> int | None:
        for attr in ("status_code", "code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        return None

    @property
    def is_rate_limit(self) -> bool:
        return self.status_code == 429

    @property
    def is_server_error(self) -> bool:
        return self.status_code is not None and 500 <= self.status_code < 600

    @property
    def is_timeout(self) -> bool:
        return "timeout" in type(self.original).__name__.lower()


def _usage_dict(
    input_tokens: int,
    output_tokens: int,
    *,
    cached_input_tokens: int = 0,
) -> dict[str, Any]:
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(input_tokens) + int(output_tokens),
        "cached_input_tokens": int(cached_input_tokens),
        "thinking_tokens": 0,
        "estimated": False,
    }


def _json_mode_instruction(response_schema: dict[object, object] | None) -> str:
    instruction = (
        "You must answer with a single valid JSON object only — no markdown "
        "fences, no commentary before or after it."
    )
    if response_schema:
        instruction += (
            "\nThe JSON object must conform to this schema:\n"
            + json.dumps(response_schema, ensure_ascii=False)
        )
    return instruction


class AnthropicProviderClient:
    """Lazy anthropic.Anthropic wrapper with prompt caching on the system block."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # lazy import: optional at runtime, heavy at import

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def _is_deprecated_temperature_error(exc: BaseException) -> bool:
        # Newer Claude models reject the temperature parameter outright
        # (400 invalid_request_error "`temperature` is deprecated for this
        # model.") — the only recovery is to retry without it.
        return (
            getattr(exc, "status_code", None) == 400
            and "temperature" in str(exc)
            and "deprecated" in str(exc)
        )

    def generate(self, request: GenerateRequest) -> GenerateResult:
        client = self._get_client()
        system_text = request.system_instruction or ""
        if request.response_mime_type == "application/json":
            # Anthropic has no response_mime_type; JSON mode is instructed.
            system_text = (
                f"{system_text}\n\n{_json_mode_instruction(request.response_schema)}"
            ).strip()

        kwargs: dict[str, Any] = {
            "model": request.model,
            # Anthropic requires max_tokens explicitly.
            "max_tokens": request.max_output_tokens or 1024,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if system_text:
            # Ephemeral cache_control lets repeated turns reuse the (large,
            # mostly static) system prompt instead of re-billing it each time.
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if request.timeout_ms:
            kwargs["timeout"] = request.timeout_ms / 1000.0

        try:
            response = client.messages.create(**kwargs)
        except Exception as exc:
            if not self._is_deprecated_temperature_error(exc):
                raise ProviderError("anthropic", request.model, exc) from exc
            logger.info(
                "anthropic model %s deprecates temperature; retrying without it",
                request.model,
            )
            kwargs.pop("temperature", None)
            try:
                response = client.messages.create(**kwargs)
            except Exception as retry_exc:
                raise ProviderError("anthropic", request.model, retry_exc) from retry_exc

        text = "".join(
            getattr(block, "text", "") for block in (response.content or [])
        ).strip()
        usage_obj = getattr(response, "usage", None)
        input_tokens = int(getattr(usage_obj, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage_obj, "output_tokens", 0) or 0)
        cached = int(getattr(usage_obj, "cache_read_input_tokens", 0) or 0)
        return GenerateResult(
            text=text,
            usage=_usage_dict(input_tokens, output_tokens, cached_input_tokens=cached),
            raw=response,
        )


class OpenAIProviderClient:
    """Lazy openai.OpenAI wrapper (chat completions)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import openai  # lazy import: optional at runtime, heavy at import

            self._client = openai.OpenAI(api_key=self._api_key)
        return self._client

    def generate(self, request: GenerateRequest) -> GenerateResult:
        client = self._get_client()
        system_text = request.system_instruction or ""
        json_mode = request.response_mime_type == "application/json"
        if json_mode and request.response_schema:
            # json_object mode needs no schema, but passing it in the system
            # text keeps the output shaped like the Gemini-JSON call sites.
            system_text = (
                f"{system_text}\n\n{_json_mode_instruction(request.response_schema)}"
            ).strip()

        messages: list[dict[str, str]] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": request.prompt})

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_output_tokens:
            kwargs["max_tokens"] = request.max_output_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if request.timeout_ms:
            kwargs["timeout"] = request.timeout_ms / 1000.0

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise ProviderError("openai", request.model, exc) from exc

        text = ""
        if response.choices:
            text = (response.choices[0].message.content or "").strip()
        usage_obj = getattr(response, "usage", None)
        input_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
        details = getattr(usage_obj, "prompt_tokens_details", None)
        cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
        return GenerateResult(
            text=text,
            usage=_usage_dict(input_tokens, output_tokens, cached_input_tokens=cached),
            raw=response,
        )


class ProviderRouter:
    """Holds one client per configured provider + per-(provider, model) cooldowns.

    A provider without an API key simply has no client: ``client_for`` returns
    None and the pool walk skips that candidate, so a deployment with only
    GEMINI_API_KEY keeps working unchanged.
    """

    def __init__(
        self,
        *,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
    ) -> None:
        self._clients: dict[str, ProviderClient] = {}
        if anthropic_api_key:
            self._clients["anthropic"] = AnthropicProviderClient(anthropic_api_key)
        if openai_api_key:
            self._clients["openai"] = OpenAIProviderClient(openai_api_key)
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._lock = Lock()

    def client_for(self, provider: str) -> ProviderClient | None:
        return self._clients.get(provider)

    def cool_down(self, provider: str, model: str, seconds: float) -> None:
        with self._lock:
            self._cooldowns[(provider, model)] = time.monotonic() + seconds

    def is_cooling_down(self, provider: str, model: str) -> bool:
        with self._lock:
            until = self._cooldowns.get((provider, model))
            if until is None:
                return False
            if until <= time.monotonic():
                del self._cooldowns[(provider, model)]
                return False
            return True
