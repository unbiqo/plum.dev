"""LLM structured insight extractor (Phase B1, §10).

Runs on the ``insight_extractor`` model profile (see ``config.MODEL_PROFILES``) with a
strict JSON schema. Extracts soft sales insights — pain, budget signals, urgency,
hidden objection, intent vector, funnel stage — from the current message plus recent
history. The LLM is injected as a coroutine (``llm_call``); this module never imports
``gemini_service``.

MUST NOT run on roleplay turns (§10.3.6) — the caller (``shadow_profiler``) guarantees
that via an early roleplay return. Never raises: invalid JSON, missing keys, or enum
violations yield ``None`` (warning logged), so the intelligence layer simply records
``extractor_no_signal``.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

URGENCY_VALUES = ("low", "medium", "high", "unknown")
STAGE_VALUES = ("awareness", "consideration", "decision", "unknown")

# Insight fields in canonical order (schema keys).
INSIGHT_FIELDS = (
    "pain",
    "budget_signals",
    "urgency",
    "hidden_objection",
    "client_intent_vector",
    "stage",
)

_ENUM_FIELDS = {"urgency": URGENCY_VALUES, "stage": STAGE_VALUES}

# google-genai response_schema (subset of OpenAPI 3 schema the API accepts).
INSIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pain": {
            "type": "string",
            "nullable": True,
            "description": "Главная боль клиента одной фразой, только если она прозвучала явно.",
        },
        "budget_signals": {
            "type": "string",
            "nullable": True,
            "description": "Сигналы о бюджете: суммы, торг, 'дорого', наличие/отсутствие бюджета.",
        },
        "urgency": {
            "type": "string",
            "enum": list(URGENCY_VALUES),
            "description": "Срочность внедрения: low/medium/high; unknown если сигнала нет.",
        },
        "hidden_objection": {
            "type": "string",
            "nullable": True,
            "description": (
                "Осторожная гипотеза о НЕвысказанном возражении клиента "
                "(только если из истории есть основания)."
            ),
        },
        "client_intent_vector": {
            "type": "string",
            "nullable": True,
            "description": (
                "Гипотеза, куда движется интент клиента (к покупке, к сравнению, "
                "к отказу, к демо) — только при наличии оснований."
            ),
        },
        "stage": {
            "type": "string",
            "enum": list(STAGE_VALUES),
            "description": (
                "Стадия воронки: awareness (знакомится), consideration (сравнивает/выбирает), "
                "decision (готов к шагу: цена, демо, старт); unknown если неясно."
            ),
        },
    },
    "required": list(INSIGHT_FIELDS),
}

INSIGHT_EXTRACTOR_SYSTEM_PROMPT = """Ты — аналитик продаж компании Dami Works (AI-автоматизация для бизнеса). По переписке менеджера с клиентом ты извлекаешь скрытые сигналы для менеджера.

Правила:
- pain, budget_signals, urgency, stage — ТОЛЬКО из явно сказанного клиентом. Никаких домыслов.
- hidden_objection и client_intent_vector — осторожные гипотезы о невысказанном: заполняй их только когда из истории диалога есть реальные основания (например, клиент обходит тему цены, сравнивает, тянет время).
- Если сигнала нет — ставь null (для enum-полей — "unknown").
- Пиши коротко, по-русски, одной фразой на поле.
- Ответ — строго один JSON-объект по заданной схеме, без пояснений и markdown."""

_HISTORY_TAIL = 6
_PROFILE_SNAPSHOT_FIELDS = (
    "business_niche",
    "offer_type",
    "lead_volume_count",
    "lead_volume_period",
    "average_check",
    "operators_count",
    "crm_or_tracking_tool",
    "decision_maker_role",
    "urgency",
    "budget_sensitivity",
)
_PROFILE_SNAPSHOT_LIST_FIELDS = ("lead_channels", "main_pains")


def _history_line(entry: Any) -> str | None:
    """Render one history entry (ChatHistoryMessage-like object or dict) as 'role: text'."""
    role = getattr(entry, "role", None)
    content = getattr(entry, "content", None)
    if role is None and isinstance(entry, dict):
        role = entry.get("role")
        content = entry.get("content")
    if not role or not content:
        return None
    speaker = "Клиент" if str(role) == "user" else "Менеджер"
    return f"{speaker}: {str(content).strip()}"


def _profile_snapshot_lines(business_profile: dict | None) -> list[str]:
    """Compact snapshot of already-known profile facts (wrapped values and lists)."""
    if not isinstance(business_profile, dict):
        return []
    lines: list[str] = []
    for field in _PROFILE_SNAPSHOT_FIELDS:
        wrapped = business_profile.get(field)
        if isinstance(wrapped, dict):
            value = wrapped.get("value")
            if value not in (None, ""):
                lines.append(f"- {field}: {value}")
    for field in _PROFILE_SNAPSHOT_LIST_FIELDS:
        values = business_profile.get(field)
        if isinstance(values, list) and values:
            lines.append(f"- {field}: {', '.join(str(v) for v in values)}")
    return lines


def build_insight_prompt(
    message: str,
    chat_history: list | None,
    business_profile: dict | None,
) -> str:
    """Build the user prompt: recent history tail + current message + known profile snapshot."""
    parts: list[str] = []

    history_lines = [
        line for line in (_history_line(entry) for entry in (chat_history or [])[-_HISTORY_TAIL:])
        if line
    ]
    if history_lines:
        parts.append("Последние сообщения диалога:\n" + "\n".join(history_lines))

    parts.append(f"Текущее сообщение клиента:\nКлиент: {(message or '').strip()}")

    snapshot = _profile_snapshot_lines(business_profile)
    if snapshot:
        parts.append("Уже известно о клиенте (не дублируй очевидное):\n" + "\n".join(snapshot))

    return "\n\n".join(parts)


def _normalize_enum(field: str, value: Any) -> str | None:
    """Lower/strip enum values; return None when the value is outside the allowed set."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in _ENUM_FIELDS[field] else None


def parse_insights(raw_text: str) -> dict[str, Any] | None:
    """Strictly parse the extractor JSON. Returns only non-null, in-enum fields or None.

    "unknown" enum values are treated as no-signal and dropped, same as nulls.
    Never raises.
    """
    try:
        parsed = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Insight extractor returned invalid JSON: %.200r", raw_text)
        return None
    if not isinstance(parsed, dict):
        logger.warning("Insight extractor returned non-object JSON: %.200r", raw_text)
        return None

    missing = [field for field in INSIGHT_FIELDS if field not in parsed]
    if missing:
        logger.warning("Insight extractor JSON missing required keys %s: %.200r", missing, raw_text)
        return None

    insights: dict[str, Any] = {}
    for field in INSIGHT_FIELDS:
        value = parsed.get(field)
        if field in _ENUM_FIELDS:
            normalized = _normalize_enum(field, value)
            if value is not None and normalized is None:
                logger.warning(
                    "Insight extractor enum violation for %s: %.200r", field, raw_text
                )
                return None
            if normalized and normalized != "unknown":
                insights[field] = normalized
            continue
        if value is None:
            continue
        if not isinstance(value, str):
            logger.warning(
                "Insight extractor non-string value for %s: %.200r", field, raw_text
            )
            return None
        stripped = value.strip()
        if stripped:
            insights[field] = stripped

    return insights


async def extract_insights(
    *,
    message: str,
    chat_history: list | None,
    business_profile: dict | None,
    llm_call: Callable[..., Awaitable[str]],
) -> dict[str, Any] | None:
    """Run the injected LLM call and parse its output. Never raises.

    ``llm_call`` is a coroutine taking ``prompt=`` and ``system_instruction=`` and
    returning raw text. Returns a dict with only the non-null insight fields, or None
    when there is no signal / the output failed validation.
    """
    prompt = build_insight_prompt(message, chat_history, business_profile)
    try:
        raw_text = await llm_call(
            prompt=prompt,
            system_instruction=INSIGHT_EXTRACTOR_SYSTEM_PROMPT,
        )
    except Exception:
        logger.exception("Insight extractor LLM call failed (ignored, no behavior impact)")
        return None
    return parse_insights(raw_text)
