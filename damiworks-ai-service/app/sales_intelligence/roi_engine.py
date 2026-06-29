"""Deterministic ROI engine (§12). All math is Python — never LLM (§12.1, hard-limit #1).

``build_roi_result`` runs the readiness gate, extracts inputs from the business profile,
applies conservative defaults (explicitly recorded as assumptions), and produces an
``ROIResult`` with conservative/realistic/aggressive scenarios and a safely phrased summary.
Numbers are rounded to ~2 significant figures to avoid fake precision. ROI is never computed
for roleplay turns.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from .roi_readiness import assess_roi_readiness

# Scenario assumption knobs used only when the real value is missing (§12.8).
_SCENARIOS = {
    "conservative": {"leakage": 0.10, "recoverability": 0.30, "conversion": 0.10},
    "realistic": {"leakage": 0.20, "recoverability": 0.50, "conversion": 0.15},
    "aggressive": {"leakage": 0.30, "recoverability": 0.70, "conversion": 0.25},
}
_DEFAULT_MARGIN = 0.30  # assumption for light_roi when margin is unknown

_PERIOD_TO_MONTH = {"day": 30.0, "week": 4.33, "month": 1.0}

_METRIC_LABELS = {
    "average_check": "средний чек",
    "lead_volume": "сколько заявок в день или месяц",
    "conversion_rate": "конверсию в продажу",
    "gross_margin": "маржинальность",
    "leakage_or_missed_leads": "сколько обращений теряется",
}
_NEXT_FIELD_PRIORITY = ("average_check", "lead_volume", "conversion_rate", "gross_margin", "leakage_or_missed_leads")


# --- field readers ----------------------------------------------------------

def _value(profile: dict[str, Any], name: str) -> Any:
    fv = profile.get(name)
    return fv.get("value") if isinstance(fv, dict) else None


def _present(profile: dict[str, Any], name: str) -> bool:
    return _value(profile, name) not in (None, "")


def _num(profile: dict[str, Any], name: str) -> float | None:
    raw = _value(profile, name)
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if raw is None:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", str(raw))
    return float(m.group(0).replace(",", ".")) if m else None


def _fraction(profile: dict[str, Any], name: str) -> float | None:
    """Parse a rate that may be given as a percent (>1 -> /100). Clamp to [0, 1]."""
    v = _num(profile, name)
    if v is None:
        return None
    if v > 1:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def _sig2(x: float | None) -> float | None:
    if x is None:
        return None
    if x == 0:
        return 0.0
    power = math.floor(math.log10(abs(x))) - 1
    factor = 10 ** power
    return float(round(x / factor) * factor)


def _leads_per_month(profile: dict[str, Any]) -> float | None:
    count = _num(profile, "lead_volume_count")
    if count is None:
        return None
    period = str(_value(profile, "lead_volume_period") or "month").lower()
    return count * _PERIOD_TO_MONTH.get(period, 1.0)


def _average_check_value(profile: dict[str, Any]) -> float | None:
    v = _num(profile, "average_check")
    if v is None:
        return None
    # signal_analyzer stores "30" for "чек 30к"; small numbers are thousands.
    return v * 1000.0 if v < 1000 else v


def _none_result(readiness: dict[str, Any], computed_at: str) -> dict[str, Any]:
    missing = readiness.get("missing_fields") or []
    next_field = _pick_next_field(missing)
    return {
        "roi_depth": "none",
        "can_show_to_user": False,
        "calculation_confidence": readiness.get("calculation_confidence", "low"),
        "confidence_reasons": readiness.get("confidence_reasons", []),
        "scenarios": {},
        "assumptions": [],
        "missing_fields": missing,
        "warnings": ["ROI not applicable: insufficient/low-confidence data or disabled context"],
        "user_safe_summary": "",
        "next_field_for_better_accuracy": next_field,
        "should_ask_for_metric": bool(next_field),
        "metric_to_ask_next": _METRIC_LABELS.get(next_field) if next_field else None,
        "computed_at": computed_at,
        "source_fields": [],
    }


def _pick_next_field(missing: list[str]) -> str | None:
    for field in _NEXT_FIELD_PRIORITY:
        if field in missing:
            return field
    return missing[0] if missing else None


def build_roi_result(
    profile: dict[str, Any],
    scores: dict[str, Any],
    behavior: dict[str, Any],
    *,
    conversation_mode: str | None = None,
    roleplay_active: bool = False,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute a deterministic ROIResult. Pure; never uses the LLM."""
    computed_at = (now or datetime.now(timezone.utc)).isoformat()
    readiness = assess_roi_readiness(
        profile, scores, behavior, conversation_mode=conversation_mode, roleplay_active=roleplay_active
    )
    level = readiness["level"]
    if level == "none":
        return _none_result(readiness, computed_at)

    config = config or {}
    ai_monthly_cost = config.get("ai_monthly_cost")
    setup_cost = config.get("setup_cost")
    operator_hourly_cost = config.get("operator_hourly_cost")

    leads = _leads_per_month(profile)
    check = _average_check_value(profile)
    currency = str(_value(profile, "currency") or "").strip()
    unit = f" {currency}" if currency else ""

    actual_conversion = _fraction(profile, "conversion_rate")
    actual_margin = _fraction(profile, "gross_margin")
    actual_leakage = _fraction(profile, "missed_leads_estimate")
    time_saved = _num(profile, "time_saved_hours_per_month")  # rarely present

    assumptions: list[str] = []
    warnings: list[str] = []
    source_fields = [f for f in ("lead_volume_count", "average_check", "conversion_rate", "gross_margin",
                                 "missed_leads_estimate", "operators_count") if _present(profile, f)]

    margin = actual_margin
    if margin is None and level in ("light_roi", "full_roi"):
        margin = _DEFAULT_MARGIN
        assumptions.append(f"маржинальность предположена ~{int(_DEFAULT_MARGIN * 100)}% (не уточнена)")
    if actual_conversion is None:
        assumptions.append("конверсия не задана — используется консервативное предположение по сценариям")
    if actual_leakage is None:
        assumptions.append("доля теряемых обращений предположена по сценариям (низкий/средний/высокий)")
    if check is not None and _num(profile, "average_check") is not None and _num(profile, "average_check") < 1000:
        assumptions.append(f"средний чек интерпретирован как ~{int(check)}{unit}")
    if ai_monthly_cost is None:
        warnings.append("стоимость AI не задана — окупаемость/ROI% не рассчитаны")

    # rough_estimate: not enough for numbers -> qualitative only.
    can_show = level in ("light_roi", "full_roi") and check is not None and leads is not None

    scenarios: dict[str, Any] = {}
    if level in ("light_roi", "full_roi") and check is not None and leads is not None:
        for name, knobs in _SCENARIOS.items():
            leakage = actual_leakage if actual_leakage is not None else knobs["leakage"]
            conversion = actual_conversion if actual_conversion is not None else knobs["conversion"]
            recoverability = knobs["recoverability"]

            lost_revenue = leads * leakage * conversion * check
            lost_margin = lost_revenue * margin if margin is not None else None
            recoverable_margin = lost_margin * recoverability if lost_margin is not None else None
            time_value = (time_saved * operator_hourly_cost) if (time_saved and operator_hourly_cost) else 0.0

            gross = (recoverable_margin or 0.0) + time_value
            net = gross - (ai_monthly_cost or 0.0)
            payback = (setup_cost / net) if (setup_cost and net and net > 0) else None
            roi_pct = (net / ai_monthly_cost * 100.0) if (ai_monthly_cost and ai_monthly_cost > 0) else None

            notes: list[str] = []
            if actual_leakage is None:
                notes.append(f"leakage≈{int(leakage * 100)}% (предположение)")
            if actual_conversion is None:
                notes.append(f"conversion≈{int(conversion * 100)}% (предположение)")
            notes.append(f"recoverability≈{int(recoverability * 100)}% (предположение)")

            scenarios[name] = {
                "lost_revenue": _sig2(lost_revenue),
                "lost_margin_profit": _sig2(lost_margin),
                "recoverable_margin_profit": _sig2(recoverable_margin),
                "time_savings_value": _sig2(time_value) if time_value else 0.0,
                "monthly_net_effect": _sig2(net) if (recoverable_margin is not None) else None,
                "payback_period_months": round(payback, 1) if payback is not None else None,
                "roi_percentage": round(roi_pct, 0) if roi_pct is not None else None,
                "notes": notes,
            }

    next_field = _pick_next_field(readiness.get("missing_fields") or [])
    summary = _build_summary(level, can_show, scenarios, unit, assumptions, next_field)

    return {
        "roi_depth": level,
        "can_show_to_user": can_show,
        "calculation_confidence": readiness["calculation_confidence"],
        "confidence_reasons": readiness.get("confidence_reasons", []),
        "scenarios": scenarios,
        "assumptions": assumptions,
        "missing_fields": readiness.get("missing_fields") or [],
        "warnings": warnings,
        "user_safe_summary": summary,
        "next_field_for_better_accuracy": next_field,
        "should_ask_for_metric": (not can_show) and bool(next_field),
        "metric_to_ask_next": _METRIC_LABELS.get(next_field) if next_field else None,
        "computed_at": computed_at,
        "source_fields": source_fields,
    }


def _fmt(n: float | None) -> str:
    if n is None:
        return "—"
    return f"{int(n):,}".replace(",", " ")


def _build_summary(level, can_show, scenarios, unit, assumptions, next_field) -> str:
    if not can_show:
        # rough_estimate / qualitative — no numbers, just where the loss zone is.
        hint = _METRIC_LABELS.get(next_field) if next_field else "средний чек и конверсию"
        return (
            "Грубая прикидка пока без цифр: зона потерь есть (часть обращений теряется или "
            f"обрабатывается медленно). Точнее можно прикинуть, зная {hint}."
        )
    cons = scenarios.get("conservative", {})
    aggr = scenarios.get("aggressive", {})
    low = cons.get("recoverable_margin_profit") if cons.get("recoverable_margin_profit") is not None else cons.get("lost_revenue")
    high = aggr.get("recoverable_margin_profit") if aggr.get("recoverable_margin_profit") is not None else aggr.get("lost_revenue")
    return (
        f"Грубая прикидка (порядок цифр, если предположить часть теряемых обращений и их возврат): "
        f"возвращаемая прибыль ≈ {_fmt(low)}–{_fmt(high)}{unit} в месяц. "
        "Это оценка по допущениям, точнее подтвердим по CRM и перепискам."
    )
