"""Prompt Composer — Phase 4 + Phase 6 (enabled modes only).

Produces a small, safe ``response_instruction`` addon for the ENABLED conversation modes.
For every other mode — and whenever roleplay is active — it is a strict no-op, so legacy
behavior is preserved.

Enabled modes:
- Phase 4: ``simple_explainer``, ``low_fit_nurture``
- Phase 6: ``microbusiness_helper``, ``integration_discovery``

Still legacy fallback: ``light_roi_diagnostic``, ``full_roi_audit``, ``roleplay_demo``.

Only short *behavioral constraints* live here (SaaS rule: no long sales scripts in Python).
Tenant-provided per-mode addons override the internal defaults when present. The internal
defaults are TEMPORARY scaffolding until tenant config carries them.
"""
from __future__ import annotations

from typing import Any

ENABLED_MODES = (
    "simple_explainer",
    "low_fit_nurture",
    "microbusiness_helper",
    "integration_discovery",
    "light_roi_diagnostic",
    "full_roi_audit",
)

_ROI_MODES = ("light_roi_diagnostic", "full_roi_audit")

# Tenant override keys (used if present & non-empty in tenant_settings).
_TENANT_KEY = "prompt_mode_{mode}"
_TENANT_KEY_PRICE_FIRST = "prompt_mode_simple_explainer_price_first"  # historical name; price-first override

# --- internal default instructions (TEMPORARY scaffolding) ------------------

_SIMPLE_EXPLAINER = (
    "[РЕЖИМ ОБЩЕНИЯ: простое объяснение — приоритет над инструкциями по дожиму] "
    "Клиент только разбирается. Сначала ответь на его вопрос простым человеческим языком, "
    "без корпоративной квалификации. Не спрашивай про CRM, маржу, конверсию или воронку, "
    "если клиент сам о них не заговорил. Объясни Dami Works по-человечески: AI-сотрудник, "
    "который отвечает клиентам, задаёт нужные вопросы, не забывает follow-up и передаёт "
    "готовые заявки. Максимум один простой уточняющий вопрос и только если он реально "
    "полезен. Не дави и не звучи как энтерпрайз-аудит."
)

_LOW_FIT_NURTURE = (
    "[РЕЖИМ ОБЩЕНИЯ: бережный nurture — приоритет над инструкциями по дожиму] "
    "Клиент пока низкого фита. Не выдумывай ROI, не дожимай, не толкай к оформлению или "
    "полному внедрению. Честно объясни, когда AI-агент становится полезным: когда уже есть "
    "поток заявок или повторяющиеся диалоги. Предложи лёгкий следующий шаг или простое "
    "объяснение. Держи дверь открытой, без давления."
)

_MICROBUSINESS_HELPER = (
    "[РЕЖИМ ОБЩЕНИЯ: микробизнес-помощник — приоритет над инструкциями по дожиму] "
    "Говори просто и конкретно, без корпоративного словаря и тяжёлого ROI. Фокус: сэкономить "
    "время владельца и не терять клиентов. Не спрашивай про CRM, маржу или конверсию, если "
    "клиент сам о них не заговорил. Приводи практические примеры: AI отвечает в "
    "WhatsApp/Instagram/Telegram, задаёт 2–3 уточняющих вопроса, помнит про follow-up, шлёт "
    "владельцу готовую сводку, подхватывает пропущенные сообщения. Хороший угол: не нужно "
    "сразу строить сложную CRM — сначала AI-помощник, который отвечает клиентам, не забывает "
    "follow-up и передаёт понятную заявку. Максимум один простой вопрос."
)

_INTEGRATION_DISCOVERY = (
    "[РЕЖИМ ОБЩЕНИЯ: интеграционный разбор — приоритет над инструкциями по дожиму] "
    "Признай сложность систем и интеграций. Строй ответ вокруг архитектуры, а не общих "
    "продаж. Помоги наметить схему потока данных: откуда приходит заявка, где лежат данные "
    "клиента, какие системы нужно синхронизировать, какое действие должен запускать AI и куда "
    "передавать результат. Не называй точную смету без scope. Без выдуманного ROI. Максимум "
    "один вопрос про архитектуру/scope. Можешь предложить короткую схему интеграции или "
    "созвон по спецификации."
)

_PRICE_ORIENTATION = (
    "[РЕЖИМ ОБЩЕНИЯ: запрос цены — приоритет над инструкциями по дожиму] "
    "Клиент спросил про цену. Дай только ценовой ориентир (порядок/вилку), без жёсткого "
    "закрытия. Не показывай карточку заказа и не запускай анкету. Можешь задать максимум один "
    "мягкий вопрос про объём задачи, если это поможет сориентировать по цене. Не дожимай."
)

_INTEGRATION_PRICE_GUARD = (
    "Не называй точную смету без scope: сначала наметь схему интеграций, потом ориентир по цене."
)

_MODE_INSTRUCTIONS = {
    "simple_explainer": _SIMPLE_EXPLAINER,
    "low_fit_nurture": _LOW_FIT_NURTURE,
    "microbusiness_helper": _MICROBUSINESS_HELPER,
    "integration_discovery": _INTEGRATION_DISCOVERY,
}

_MODE_REASONS = {
    "simple_explainer": "simple_explainer: answer-first, plain language, no enterprise audit",
    "low_fit_nurture": "low_fit_nurture: honest, no fake ROI, no hard close",
    "microbusiness_helper": "microbusiness_helper: time-saving, practical examples, no enterprise vocab",
    "integration_discovery": "integration_discovery: architecture/data-flow framing, no estimate without scope",
}


_ROI_HEADER = "[РЕЖИМ ОБЩЕНИЯ: ROI-разбор — приоритет над инструкциями по дожиму] "


def _roi_show_instruction(conversation_mode: str, roi_result: dict[str, Any]) -> str:
    summary = (roi_result.get("user_safe_summary") or "").strip()
    assumptions = roi_result.get("assumptions") or []
    assum_line = (" Допущения: " + "; ".join(assumptions) + ".") if assumptions else ""
    next_step = (
        "Предложи следующий шаг: подтвердить цифры по CRM/перепискам, затем спецификация или короткий созвон."
        if conversation_mode == "full_roi_audit"
        else "Предложи уточнить один недостающий показатель или короткий разбор."
    )
    return (
        _ROI_HEADER
        + "Используй ТОЛЬКО эти посчитанные на Python цифры — не выдумывай, не уточняй и не пересчитывай их сам: "
        + summary
        + assum_line
        + " Говори про порядок цифр и допущения, без обещаний точных гарантий ('вы точно теряете' — запрещено)."
        + " " + next_step + " Максимум один вопрос."
    )


def _roi_metric_gap_instruction(conversation_mode: str, roi_result: dict[str, Any] | None) -> str:
    metric = (roi_result or {}).get("metric_to_ask_next") or "средний чек и конверсию"
    return (
        _ROI_HEADER
        + "Данных недостаточно для расчёта — не показывай ROI-цифры и не выдумывай их. "
        + f"Объясни простыми словами, что для грубой прикидки не хватает одного показателя ({metric}), "
        + "и при возможности мягко спроси его. Дай качественный вывод на основе уже известного, без обещаний."
    )


def _is_price_first(wow_mechanism: str | None, next_best_action_type: str | None) -> bool:
    return wow_mechanism == "checkout_or_call" and next_best_action_type == "price_orientation"


def _tenant_override(tenant_settings: dict[str, Any] | None, key: str) -> str:
    if not isinstance(tenant_settings, dict):
        return ""
    value = tenant_settings.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _noop(reason: str, mode: str | None = None) -> dict[str, Any]:
    return {"applied": False, "mode": mode, "reason": reason, "instruction": ""}


def compose_safe_mode_instruction(
    *,
    conversation_mode: str | None,
    wow_mechanism: str | None = None,
    next_best_action_type: str | None = None,
    bot_guidance: dict[str, Any] | None = None,
    tenant_settings: dict[str, Any] | None = None,
    roleplay_active: bool = False,
    roi_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an enabled-mode instruction descriptor.

    Keys: ``applied`` (bool), ``mode`` (str|None), ``reason`` (str), ``instruction`` (str).
    Non-enabled modes and roleplay turns return a no-op (``applied=False``, empty instruction).
    """
    if roleplay_active:
        return _noop("roleplay_active: prompt composer is no-op", conversation_mode)

    if conversation_mode not in ENABLED_MODES:
        return _noop("non-enabled mode: legacy fallback", conversation_mode)

    # Price-first applies uniformly across enabled modes: price orientation only, never a
    # questionnaire. (Deterministic price override, when it triggers, returns earlier in api.py.)
    if _is_price_first(wow_mechanism, next_best_action_type):
        instruction = _tenant_override(tenant_settings, _TENANT_KEY_PRICE_FIRST) or _PRICE_ORIENTATION
        if conversation_mode == "integration_discovery":
            instruction = "\n\n".join([instruction, _INTEGRATION_PRICE_GUARD])
        reason = f"{conversation_mode} + price-first: price orientation only, no hard close/card"
        return {"applied": True, "mode": conversation_mode, "reason": reason, "instruction": instruction}

    # ROI modes: show ROI only when the Python engine says can_show_to_user; otherwise a
    # metric-gap instruction (no ROI numbers, no fake precision) — hard-limits #2/#10.
    if conversation_mode in _ROI_MODES:
        if roi_result and roi_result.get("can_show_to_user"):
            instruction = _roi_show_instruction(conversation_mode, roi_result)
            reason = f"{conversation_mode}: ROI summary shown (confidence={roi_result.get('calculation_confidence')})"
        else:
            instruction = _roi_metric_gap_instruction(conversation_mode, roi_result)
            reason = f"{conversation_mode}: ROI not shown (can_show_to_user=false), metric-gap guidance"
        return {"applied": True, "mode": conversation_mode, "reason": reason, "instruction": instruction}

    instruction = _tenant_override(tenant_settings, _TENANT_KEY.format(mode=conversation_mode)) or _MODE_INSTRUCTIONS[conversation_mode]
    return {
        "applied": True,
        "mode": conversation_mode,
        "reason": _MODE_REASONS[conversation_mode],
        "instruction": instruction,
    }
