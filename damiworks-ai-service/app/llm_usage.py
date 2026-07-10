from __future__ import annotations

import contextvars
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any


MODEL_PRICING_USD_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
}

_PRICING_ENV = "MODEL_PRICING_USD_PER_1M_TOKENS_JSON"
_LLM_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "llm_usage_context",
    default=None,
)


def begin_llm_usage_context(
    *,
    instance_id: str,
    chat_id: str,
    message_id: str | None = None,
    tenant_id: str | None = None,
) -> contextvars.Token:
    return _LLM_CONTEXT.set(
        {
            "conversation_id": f"{instance_id}:{chat_id}",
            "instance_id": instance_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "tenant_id": tenant_id,
            "calls": [],
        }
    )


def end_llm_usage_context(token: contextvars.Token) -> None:
    _LLM_CONTEXT.reset(token)


def current_llm_calls() -> list[dict[str, Any]]:
    ctx = _LLM_CONTEXT.get()
    if not ctx:
        return []
    return list(ctx.get("calls") or [])


def record_llm_call(call: dict[str, Any]) -> None:
    ctx = _LLM_CONTEXT.get()
    if not ctx:
        return
    ctx.setdefault("calls", []).append(
        {
            "conversation_id": ctx.get("conversation_id"),
            "message_id": ctx.get("message_id"),
            "tenant_id": ctx.get("tenant_id"),
            "instance_id": ctx.get("instance_id"),
            **call,
        }
    )


def get_model_pricing(model_name: str) -> dict[str, float] | None:
    override = _load_pricing_override()
    if model_name in override:
        return override[model_name]
    return MODEL_PRICING_USD_PER_1M_TOKENS.get(model_name)


def calculate_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int | None = None,
    thinking_tokens: int | None = None,
) -> dict[str, Any]:
    pricing = get_model_pricing(model)
    if pricing is None:
        return {
            "input_cost_usd": None,
            "output_cost_usd": None,
            "total_cost_usd": None,
            "pricing_missing": True,
        }

    billable_input = max(0, input_tokens - int(cached_input_tokens or 0))
    # Gemini output pricing includes thinking tokens when they are reported as part
    # of output usage. Keep the field, but do not add it again here.
    billable_output = max(0, output_tokens)
    input_cost = billable_input * pricing["input"] / 1_000_000
    output_cost = billable_output * pricing["output"] / 1_000_000
    return {
        "input_cost_usd": round(input_cost, 8),
        "output_cost_usd": round(output_cost, 8),
        "total_cost_usd": round(input_cost + output_cost, 8),
        "pricing_missing": False,
        "billable_input_tokens": billable_input,
        "billable_output_tokens": billable_output,
        "thinking_tokens": thinking_tokens or 0,
    }


def usage_from_response(
    response: object,
    *,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
) -> dict[str, Any]:
    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return _estimated_usage(estimated_input_tokens, estimated_output_tokens)

    input_tokens = _usage_int(
        metadata,
        "prompt_token_count",
        "input_token_count",
        "input_tokens",
    )
    output_tokens = _usage_int(
        metadata,
        "candidates_token_count",
        "output_token_count",
        "output_tokens",
    )
    total_tokens = _usage_int(metadata, "total_token_count", "total_tokens")
    cached_input_tokens = _usage_int(
        metadata,
        "cached_content_token_count",
        "cached_input_token_count",
        "cached_input_tokens",
    )
    thinking_tokens = _usage_int(
        metadata,
        "thoughts_token_count",
        "thinking_token_count",
        "thinking_tokens",
    )

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return _estimated_usage(estimated_input_tokens, estimated_output_tokens)

    input_tokens = input_tokens if input_tokens is not None else estimated_input_tokens
    output_tokens = output_tokens if output_tokens is not None else estimated_output_tokens
    total_tokens = total_tokens if total_tokens is not None else input_tokens + output_tokens
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(total_tokens),
        "cached_input_tokens": int(cached_input_tokens or 0),
        "thinking_tokens": int(thinking_tokens or 0),
        "estimated": False,
    }


def build_llm_call_log(
    *,
    provider: str,
    task_type: str | None,
    model_profile: str | None,
    selected_model: str | None,
    model_pool: tuple[str, ...] | list[str] | None,
    usage: dict[str, Any],
    latency_ms: int,
    success: bool,
    error_type: str | None = None,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    escalation_used: bool = False,
    escalation_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = selected_model or ""
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cached = int(usage.get("cached_input_tokens") or 0)
    thinking = int(usage.get("thinking_tokens") or 0)
    cost = (
        calculate_llm_cost(
            selected,
            input_tokens,
            output_tokens,
            cached_input_tokens=cached,
            thinking_tokens=thinking,
        )
        if selected
        else {
            "input_cost_usd": None,
            "output_cost_usd": None,
            "total_cost_usd": None,
            "pricing_missing": True,
        }
    )
    billable_input = int(cost.get("billable_input_tokens", max(0, input_tokens - cached)) or 0)
    billable_output = int(cost.get("billable_output_tokens", output_tokens) or 0)
    return {
        "call_id": str(uuid.uuid4()),
        "provider": provider,
        "task_type": task_type or model_profile or "default",
        "model_profile": model_profile,
        "selected_model": selected_model,
        "model_pool": list(model_pool or []),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(usage.get("total_tokens") or input_tokens + output_tokens),
        "cached_input_tokens": cached,
        "thinking_tokens": thinking,
        "billable_input_tokens": billable_input,
        "billable_output_tokens": billable_output,
        "estimated": bool(usage.get("estimated")),
        "input_cost_usd": cost.get("input_cost_usd"),
        "output_cost_usd": cost.get("output_cost_usd"),
        "total_cost_usd": cost.get("total_cost_usd"),
        "currency": "USD",
        "pricing_missing": bool(cost.get("pricing_missing")),
        "latency_ms": latency_ms,
        "success": success,
        "error_type": error_type,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "escalation_used": escalation_used,
        "escalation_reason": escalation_reason,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def aggregate_llm_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    total_input = sum(_as_int(c.get("input_tokens")) for c in calls)
    total_output = sum(_as_int(c.get("output_tokens")) for c in calls)
    total_tokens = sum(_as_int(c.get("total_tokens")) for c in calls)
    known_costs = [float(c["total_cost_usd"]) for c in calls if c.get("total_cost_usd") is not None]
    estimated_costs = [
        float(c["total_cost_usd"])
        for c in calls
        if c.get("total_cost_usd") is not None and c.get("estimated")
    ]

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "total_cost_usd": round(sum(known_costs), 8) if known_costs else None,
        "estimated_cost_usd": round(sum(estimated_costs), 8) if estimated_costs else 0.0,
        "has_estimated_usage": any(bool(c.get("estimated")) for c in calls),
        "has_missing_pricing": any(bool(c.get("pricing_missing")) for c in calls),
        "llm_call_count": len(calls),
        "fallback_count": sum(1 for c in calls if c.get("fallback_used")),
        "escalation_count": sum(1 for c in calls if c.get("escalation_used")),
        "model_count": len({c.get("selected_model") for c in calls if c.get("selected_model")}),
        "slowest_call_ms": max((_as_int(c.get("latency_ms")) for c in calls), default=0),
        "by_model": _aggregate_groups(calls, ("selected_model",), "model"),
        "by_task": _aggregate_groups(calls, ("task_type", "model_profile", "selected_model"), "task_type"),
        "calls": calls,
    }


def compact_conversation_cost(cost: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_input_tokens": cost.get("total_input_tokens", 0),
        "total_output_tokens": cost.get("total_output_tokens", 0),
        "total_tokens": cost.get("total_tokens", 0),
        "total_cost_usd": cost.get("total_cost_usd"),
        "has_estimated_usage": bool(cost.get("has_estimated_usage")),
        "has_missing_pricing": bool(cost.get("has_missing_pricing")),
        "llm_call_count": cost.get("llm_call_count", 0),
        "fallback_count": cost.get("fallback_count", 0),
        "escalation_count": cost.get("escalation_count", 0),
        "model_count": cost.get("model_count", 0),
        "slowest_call_ms": cost.get("slowest_call_ms", 0),
    }


def _estimated_usage(input_tokens: int, output_tokens: int) -> dict[str, Any]:
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(input_tokens) + int(output_tokens),
        "cached_input_tokens": 0,
        "thinking_tokens": 0,
        "estimated": True,
    }


def _usage_int(metadata: object, *names: str) -> int | None:
    for name in names:
        value = metadata.get(name) if isinstance(metadata, dict) else getattr(metadata, name, None)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _aggregate_groups(calls: list[dict[str, Any]], keys: tuple[str, ...], label_key: str) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for call in calls:
        group_key = tuple(call.get(key) for key in keys)
        if group_key not in groups:
            item = {label_key: group_key[0] or "unknown"}
            for index, key in enumerate(keys[1:], start=1):
                item[key if key != "selected_model" else "model"] = group_key[index] or "unknown"
            item.update(
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": None,
                    "pricing_missing": False,
                    "estimated": False,
                }
            )
            groups[group_key] = item
        item = groups[group_key]
        item["calls"] += 1
        item["input_tokens"] += _as_int(call.get("input_tokens"))
        item["output_tokens"] += _as_int(call.get("output_tokens"))
        item["total_tokens"] += _as_int(call.get("total_tokens"))
        item["pricing_missing"] = bool(item["pricing_missing"] or call.get("pricing_missing"))
        item["estimated"] = bool(item["estimated"] or call.get("estimated"))
        if call.get("total_cost_usd") is not None:
            item["cost_usd"] = round(float(item["cost_usd"] or 0) + float(call["total_cost_usd"]), 8)
    return sorted(groups.values(), key=lambda item: str(item.get(label_key) or ""))


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _load_pricing_override() -> dict[str, dict[str, float]]:
    raw = os.getenv(_PRICING_ENV, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    result: dict[str, dict[str, float]] = {}
    if not isinstance(parsed, dict):
        return result
    for model, prices in parsed.items():
        if not isinstance(prices, dict):
            continue
        try:
            result[str(model)] = {
                "input": float(prices["input"]),
                "output": float(prices["output"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return result
