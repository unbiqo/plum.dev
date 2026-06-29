from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from threading import Lock

from .config import GeminiApiKey


MINUTE_SECONDS = 60
DAY_SECONDS = 24 * 60 * 60
DEFAULT_TEXT_TPM = 250_000
DEFAULT_TEXT_RPM = 1_000
DEFAULT_TEXT_RPD = 100_000
DEFAULT_EMBEDDING_RPM = 100
DEFAULT_EMBEDDING_TPM = 30_000
DEFAULT_EMBEDDING_RPD = 1_000
RPD_COOLDOWN_SECONDS = DAY_SECONDS
RPM_COOLDOWN_SECONDS = MINUTE_SECONDS
UNKNOWN_QUOTA_COOLDOWN_SECONDS = 10 * MINUTE_SECONDS
FAILURE_COOLDOWN_SECONDS = 5 * MINUTE_SECONDS


@dataclass(frozen=True)
class ModelLimits:
    rpm: int
    tpm: int
    rpd: int


@dataclass(frozen=True)
class UsageEvent:
    id: str
    timestamp: float
    tokens: int


@dataclass(frozen=True)
class GeminiQuotaLease:
    id: str
    key_name: str
    model: str
    estimated_tokens: int


class GeminiQuotaExhausted(RuntimeError):
    pass


TEXT_MODEL_LIMITS = {
    "gemini-2.5-flash-lite": ModelLimits(
        rpm=DEFAULT_TEXT_RPM,
        tpm=DEFAULT_TEXT_TPM,
        rpd=DEFAULT_TEXT_RPD,
    ),
}
EMBEDDING_MODEL_LIMITS = {
    "text-embedding-004": ModelLimits(
        rpm=DEFAULT_EMBEDDING_RPM,
        tpm=DEFAULT_EMBEDDING_TPM,
        rpd=DEFAULT_EMBEDDING_RPD,
    ),
    "gemini-embedding-001": ModelLimits(
        rpm=DEFAULT_EMBEDDING_RPM,
        tpm=DEFAULT_EMBEDDING_TPM,
        rpd=DEFAULT_EMBEDDING_RPD,
    ),
    "gemini-embedding-2": ModelLimits(
        rpm=DEFAULT_EMBEDDING_RPM,
        tpm=DEFAULT_EMBEDDING_TPM,
        rpd=DEFAULT_EMBEDDING_RPD,
    ),
}
MODEL_LIMITS = TEXT_MODEL_LIMITS | EMBEDDING_MODEL_LIMITS


def estimate_tokens(*parts: str, max_output_tokens: int | None = None) -> int:
    text_tokens = sum(max(1, math.ceil(len(part) / 4)) for part in parts if part)
    output_tokens = max_output_tokens if max_output_tokens is not None else 384
    return max(1, text_tokens + output_tokens)


def estimate_embedding_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def normalize_model_name(model: str) -> str:
    return model.removeprefix("models/").strip()


class GeminiQuotaManager:
    def __init__(self, api_keys: tuple[GeminiApiKey, ...]) -> None:
        if not api_keys:
            raise RuntimeError("At least one Gemini API key is required")

        self._api_keys = api_keys
        self._usage: dict[tuple[str, str], list[UsageEvent]] = {}
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._lock = Lock()

    def reserve(
        self,
        models: tuple[str, ...],
        estimated_tokens: int,
        *,
        skipped: set[tuple[str, str]] | None = None,
    ) -> GeminiQuotaLease:
        skipped = skipped or set()
        normalized_models = tuple(dict.fromkeys(model.strip() for model in models if model.strip()))
        if not normalized_models:
            raise GeminiQuotaExhausted("No Gemini models are configured")

        now = time.time()
        with self._lock:
            self._cleanup(now)
            option = self._select_option(
                normalized_models,
                estimated_tokens,
                now=now,
                skipped=skipped,
            )
            if option is None:
                raise GeminiQuotaExhausted(self._exhausted_message(now))

            score, key_index, model_priority, api_key, model = option
            event = UsageEvent(
                id=uuid.uuid4().hex,
                timestamp=now,
                tokens=estimated_tokens,
            )
            pair = (api_key.name, normalize_model_name(model))
            self._usage.setdefault(pair, []).append(event)
            return GeminiQuotaLease(
                id=event.id,
                key_name=api_key.name,
                model=model,
                estimated_tokens=estimated_tokens,
            )

    def reserve_for_key(
        self,
        *,
        key_name: str,
        model: str,
        estimated_tokens: int,
    ) -> GeminiQuotaLease:
        model_name = normalize_model_name(model)
        now = time.time()
        with self._lock:
            self._cleanup(now)
            pair = (key_name, model_name)
            if self._cooldowns.get(pair, 0) > now:
                raise GeminiQuotaExhausted(
                    f"Gemini key/model pair {key_name}/{model_name} is cooling down"
                )

            limits = limits_for_model(model_name)
            minute_events = self._events_since(pair, now - MINUTE_SECONDS)
            day_events = self._events_since(pair, now - DAY_SECONDS)
            if len(minute_events) + 1 > limits.rpm:
                raise GeminiQuotaExhausted(
                    f"Gemini key/model pair {key_name}/{model_name} is at local RPM limit"
                )
            if sum(event.tokens for event in minute_events) + estimated_tokens > limits.tpm:
                raise GeminiQuotaExhausted(
                    f"Gemini key/model pair {key_name}/{model_name} is at local TPM limit"
                )
            if len(day_events) + 1 > limits.rpd:
                raise GeminiQuotaExhausted(
                    f"Gemini key/model pair {key_name}/{model_name} is at local RPD limit"
                )

            event = UsageEvent(
                id=uuid.uuid4().hex,
                timestamp=now,
                tokens=estimated_tokens,
            )
            self._usage.setdefault(pair, []).append(event)
            return GeminiQuotaLease(
                id=event.id,
                key_name=key_name,
                model=model,
                estimated_tokens=estimated_tokens,
            )

    def complete(self, lease: GeminiQuotaLease, actual_tokens: int | None = None) -> None:
        if actual_tokens is None or actual_tokens <= 0:
            return

        pair = (lease.key_name, normalize_model_name(lease.model))
        with self._lock:
            events = self._usage.get(pair, [])
            self._usage[pair] = [
                (
                    UsageEvent(
                        id=event.id,
                        timestamp=event.timestamp,
                        tokens=actual_tokens,
                    )
                    if event.id == lease.id
                    else event
                )
                for event in events
            ]

    def refund(self, lease: GeminiQuotaLease) -> None:
        pair = (lease.key_name, normalize_model_name(lease.model))
        with self._lock:
            self._usage[pair] = [
                event for event in self._usage.get(pair, []) if event.id != lease.id
            ]

    def cool_down(self, lease: GeminiQuotaLease, exc: BaseException) -> None:
        message = str(exc).lower()
        if "per day" in message or "requestsperday" in message or "rpd" in message:
            seconds = RPD_COOLDOWN_SECONDS
        elif "per minute" in message or "requestsperminute" in message or "rpm" in message:
            seconds = RPM_COOLDOWN_SECONDS
        elif "resource_exhausted" in message or "429" in message or "quota" in message:
            seconds = UNKNOWN_QUOTA_COOLDOWN_SECONDS
        else:
            seconds = FAILURE_COOLDOWN_SECONDS

        pair = (lease.key_name, normalize_model_name(lease.model))
        with self._lock:
            self._cooldowns[pair] = time.time() + seconds

    def _select_option(
        self,
        models: tuple[str, ...],
        estimated_tokens: int,
        *,
        now: float,
        skipped: set[tuple[str, str]],
    ) -> tuple[float, int, int, GeminiApiKey, str] | None:
        options: list[tuple[float, int, int, GeminiApiKey, str]] = []
        for model_priority, model in enumerate(models):
            model_name = normalize_model_name(model)
            limits = limits_for_model(model_name)
            for key_index, api_key in enumerate(self._api_keys):
                pair = (api_key.name, model_name)
                if pair in skipped:
                    continue

                if self._cooldowns.get(pair, 0) > now:
                    continue

                minute_events = self._events_since(pair, now - MINUTE_SECONDS)
                day_events = self._events_since(pair, now - DAY_SECONDS)
                minute_requests = len(minute_events)
                minute_tokens = sum(event.tokens for event in minute_events)
                day_requests = len(day_events)

                if minute_requests + 1 > limits.rpm:
                    continue
                if minute_tokens + estimated_tokens > limits.tpm:
                    continue
                if day_requests + 1 > limits.rpd:
                    continue

                request_utilization = (minute_requests + 1) / limits.rpm
                token_utilization = (minute_tokens + estimated_tokens) / limits.tpm
                day_utilization = (day_requests + 1) / limits.rpd
                pressure = max(
                    request_utilization,
                    token_utilization,
                    day_utilization,
                )
                score = pressure + (model_priority * 0.03) + (key_index * 0.001)
                options.append((score, key_index, model_priority, api_key, model))

        if not options:
            return None

        return min(options, key=lambda option: (option[0], option[2], option[1]))

    def _cleanup(self, now: float) -> None:
        oldest_allowed = now - DAY_SECONDS
        for pair, events in list(self._usage.items()):
            self._usage[pair] = [
                event for event in events if event.timestamp >= oldest_allowed
            ]

        for pair, until in list(self._cooldowns.items()):
            if until <= now:
                del self._cooldowns[pair]

    def _events_since(self, pair: tuple[str, str], since: float) -> list[UsageEvent]:
        return [
            event
            for event in self._usage.get(pair, [])
            if event.timestamp >= since
        ]

    def _exhausted_message(self, now: float) -> str:
        reset_at = self._next_reset_at(now)
        if reset_at is None:
            return "All configured Gemini key/model pairs are currently unavailable"

        wait_seconds = max(1, math.ceil(reset_at - now))
        return (
            "All configured Gemini key/model pairs are at local RPM/TPM/RPD limits; "
            f"next local slot opens in about {wait_seconds} seconds"
        )

    def _next_reset_at(self, now: float) -> float | None:
        candidates: list[float] = []
        candidates.extend(until for until in self._cooldowns.values() if until > now)
        for events in self._usage.values():
            candidates.extend(event.timestamp + MINUTE_SECONDS for event in events)
            candidates.extend(event.timestamp + DAY_SECONDS for event in events)

        future_candidates = [candidate for candidate in candidates if candidate > now]
        if not future_candidates:
            return None

        return min(future_candidates)


def limits_for_model(model_name: str) -> ModelLimits:
    normalized = normalize_model_name(model_name)
    if normalized in MODEL_LIMITS:
        return MODEL_LIMITS[normalized]

    if "embedding" in normalized:
        return ModelLimits(
            rpm=DEFAULT_EMBEDDING_RPM,
            tpm=DEFAULT_EMBEDDING_TPM,
            rpd=DEFAULT_EMBEDDING_RPD,
        )

    if "lite" in normalized:
        return ModelLimits(rpm=DEFAULT_TEXT_RPM, tpm=DEFAULT_TEXT_TPM, rpd=DEFAULT_TEXT_RPD)

    return ModelLimits(rpm=DEFAULT_TEXT_RPM, tpm=DEFAULT_TEXT_TPM, rpd=DEFAULT_TEXT_RPD)
