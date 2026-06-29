"""Conversation Strategy Engine (§3, §9.2, §11).

Pure, deterministic. Selects ``conversation_mode`` from scores + profile + behavior, evaluates
the question budget, derives ``next_best_action`` and ``bot_guidance``, and composes the full
``strategy_result`` (including ``wow_mechanism`` from the wow router). ``logging_reasons`` carry
the mode rationale plus a compact score summary and the key drivers, so a chosen
mode/mechanism is explainable.
"""
from __future__ import annotations

from typing import Any

from . import wow_router
from .question_budget import evaluate_budget, must_give_value
from .scoring import _has, _num, _value  # internal profile readers

_ASK_TYPES = {"ask_simple_context_question", "ask_business_context", "ask_metric_for_roi"}


def _select_mode(profile: dict[str, Any], scores: dict[str, int], behavior: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    pains = profile.get("main_pains") or []
    integrations = profile.get("integration_needs") or []
    channels = profile.get("lead_channels") or []
    lead_volume = _num(profile, "lead_volume_count")
    operators = _num(profile, "operators_count")
    owner_involved = _value(profile, "owner_involved") is True
    has_crm = _has(profile, "crm_or_tracking_tool")
    has_check = _has(profile, "average_check")

    roi_potential = scores["roi_potential_score"]
    data_readiness = scores["data_readiness_score"]
    friction = scores["conversation_friction_score"]

    # 1. explicit roleplay / demo / test-drive intent
    if behavior.get("roleplay_intent") or behavior.get("asked_for_demo"):
        reasons.append("explicit roleplay/demo intent")
        return "roleplay_demo", reasons

    # 2. anti-fit: technical DIY / open-source / below-minimum budget
    if behavior.get("diy_signal"):
        reasons.append("anti-fit: DIY/open-source/free intent")
        return "low_fit_nurture", reasons

    # 3. anti-fit: explicit no-business / no-leads / just-looking
    if behavior.get("low_fit_signal"):
        reasons.append("anti-fit: no business / no lead flow / just looking")
        return "low_fit_nurture", reasons

    # 4. integration discovery — internal-system integration dominates architecture
    if integrations:
        reasons.append(f"integration_needs present ({integrations}); architecture-led")
        return "integration_discovery", reasons

    # 5. full ROI audit — high flow + structural maturity + low friction
    if (
        lead_volume is not None and lead_volume >= 50
        and friction < 50
        and data_readiness >= 40
        and (has_crm or (operators is not None and operators >= 2))
    ):
        reasons.append("high lead volume + CRM/team + data_readiness + low friction")
        return "full_roi_audit", reasons

    # 6. light ROI diagnostic — regular flow/check or clear sales pain + some data
    if friction < 50 and roi_potential >= 40 and data_readiness >= 25 and (
        (lead_volume is not None and has_check) or any(p in pains for p in ("losing_leads", "slow_response"))
    ):
        reasons.append("regular flow/check or sales pain + partial data")
        return "light_roi_diagnostic", reasons

    # 7. microbusiness helper — owner-run, small/unknown team, operational pain
    if owner_involved or (operators is not None and operators <= 1) or any(
        p in pains for p in ("not_enough_time", "owner_overload", "chaos_in_chats", "forgetting_followups")
    ) or (channels and not has_crm):
        reasons.append("owner-involved / small team / operational pain")
        return "microbusiness_helper", reasons

    # 8. default — still explaining value / low context
    reasons.append("default: low context / still explaining value")
    return "simple_explainer", reasons


_TONE_BY_MODE = {
    "simple_explainer": "simple_friendly",
    "microbusiness_helper": "simple_supportive",
    "light_roi_diagnostic": "consultative",
    "full_roi_audit": "expert_analytical",
    "integration_discovery": "architectural",
    "roleplay_demo": "playful_confident",
    "low_fit_nurture": "light_no_pressure",
}

_AVOID_BY_MODE = {
    "simple_explainer": ["маржа", "конверсия", "воронка"],
    "microbusiness_helper": ["маржа", "конверсия", "сложный ROI"],
    "light_roi_diagnostic": ["сложный аудит"],
    "full_roi_audit": [],
    "integration_discovery": ["преждевременный ROI"],
    "roleplay_demo": ["цены", "квалификация"],
    "low_fit_nurture": ["цены", "сложный ROI", "давление"],
}

_ANGLE_BY_MODE = {
    "simple_explainer": "объяснить ценность простыми словами, найти первый контекст",
    "microbusiness_helper": "снять рутину с владельца и не терять диалоги",
    "light_roi_diagnostic": "показать порядок потерь быстрым расчётом-диапазоном",
    "full_roi_audit": "собрать метрики и показать сценарии ROI, вести к спецификации",
    "integration_discovery": "показать, как встроить AI во внутренние процессы",
    "roleplay_demo": "предложить тест-драйв: показать, как AI продаёт в нише клиента",
    "low_fit_nurture": "объяснить, когда AI станет актуальным, без давления",
}

_TARGET_FIELD_BY_MODE = {
    "simple_explainer": "business_niche",
    "microbusiness_helper": "lead_channels",
    "light_roi_diagnostic": "average_check",
    "full_roi_audit": "conversion_rate",
    "integration_discovery": "integration_needs",
    "roleplay_demo": None,
    "low_fit_nurture": None,
}

_DEFAULT_NBA_BY_MODE = {
    "simple_explainer": "ask_simple_context_question",
    "microbusiness_helper": "ask_business_context",
    "light_roi_diagnostic": "ask_metric_for_roi",
    "full_roi_audit": "ask_metric_for_roi",
    "integration_discovery": "offer_integration_discovery",
    "roleplay_demo": "offer_roleplay",
    "low_fit_nurture": "nurture",
}


def _next_best_action(mode: str, behavior: dict[str, Any], scores: dict[str, int], stop_questioning: bool) -> dict[str, Any]:
    if mode == "roleplay_demo":
        nba_type = "offer_roleplay"
    elif behavior.get("asked_price"):
        # High buying readiness -> close; otherwise price orientation only (no questionnaire).
        nba_type = (
            "offer_call_or_specification"
            if scores["buying_readiness_score"] >= 45
            else "price_orientation"
        )
    elif stop_questioning:
        nba_type = "simplify" if scores["conversation_friction_score"] >= 50 else "give_value"
    else:
        nba_type = _DEFAULT_NBA_BY_MODE.get(mode, "answer_only")
        if behavior.get("asked_how_it_works") and mode == "simple_explainer":
            nba_type = "answer_only"

    return {
        "type": nba_type,
        "value_message": None,  # copy is composed by prompt_composer (Phase 6)
        "question": None,
        "target_field": _TARGET_FIELD_BY_MODE.get(mode),
        "should_ask_now": (not stop_questioning) and nba_type in _ASK_TYPES,
    }


def _roi_depth(mode: str, scores: dict[str, int]) -> str:
    # Phase 3: no real calculation; cap at rough_estimate (ROI Engine lands in Phase 5).
    if mode == "full_roi_audit":
        return "rough_estimate"
    if mode == "light_roi_diagnostic":
        return "rough_estimate" if scores["data_readiness_score"] >= 25 else "none"
    return "none"


def _score_summary(scores: dict[str, int]) -> str:
    return (
        "scores: "
        f"icp={scores['icp_fit_score']} roi={scores['roi_potential_score']} "
        f"pain={scores['operational_pain_score']} data={scores['data_readiness_score']} "
        f"friction={scores['conversation_friction_score']} buy={scores['buying_readiness_score']} "
        f"ai={scores['ai_fit_score']} integ={scores['integration_complexity_score']}"
    )


def _drivers(profile: dict[str, Any], behavior: dict[str, Any]) -> str:
    parts: list[str] = []
    lead_volume = _num(profile, "lead_volume_count")
    if lead_volume is not None:
        parts.append(f"lead_volume={lead_volume}")
    operators = _num(profile, "operators_count")
    if operators is not None:
        parts.append(f"operators={operators}")
    if _has(profile, "average_check"):
        parts.append("avg_check")
    if _has(profile, "crm_or_tracking_tool"):
        parts.append(f"crm={_value(profile, 'crm_or_tracking_tool')}")
    if _value(profile, "owner_involved") is True:
        parts.append("owner_involved")
    for key in ("lead_channels", "main_pains", "integration_needs"):
        vals = profile.get(key) or []
        if vals:
            parts.append(f"{key}={vals}")
    for flag in ("asked_price", "roleplay_intent", "asked_for_demo", "diy_signal", "low_fit_signal", "irritated_by_questions"):
        if behavior.get(flag):
            parts.append(flag)
    return "drivers: " + (", ".join(parts) if parts else "none")


def resolve_strategy(
    *,
    profile: dict[str, Any],
    scores: dict[str, int],
    behavior: dict[str, Any],
    prior_qualification_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the full ``strategy_result`` (§9.2)."""
    mode, reasons = _select_mode(profile, scores, behavior)

    prior_budget = (prior_qualification_state or {}).get("question_budget")
    budget = evaluate_budget(mode, prior_budget)
    stop_questioning = must_give_value(budget) or scores["conversation_friction_score"] >= 50

    wow = wow_router.resolve_wow_mechanism(profile, scores, mode, behavior)
    roi_depth = _roi_depth(mode, scores)
    nba = _next_best_action(mode, behavior, scores, stop_questioning)

    # Price-first without high buying readiness: keep the commercial signal (wow) but give a
    # price orientation only — no hard close, no checkout card, no questionnaire.
    price_orientation_only = bool(behavior.get("asked_price")) and scores["buying_readiness_score"] < 45

    guidance = {
        "tone": _TONE_BY_MODE.get(mode, "simple_friendly"),
        "avoid_topics": list(_AVOID_BY_MODE.get(mode, [])),
        "recommended_angle": _ANGLE_BY_MODE.get(mode, ""),
        "should_offer_roi_audit": mode in ("light_roi_diagnostic", "full_roi_audit"),
        "should_offer_roleplay": mode == "roleplay_demo" or wow == "roleplay_demo" or (
            mode in ("simple_explainer", "microbusiness_helper") and scores["data_readiness_score"] < 25
        ),
        "should_offer_call": scores["buying_readiness_score"] >= 45 or mode == "full_roi_audit",
        "should_simplify": mode in ("simple_explainer", "low_fit_nurture") or scores["conversation_friction_score"] >= 50,
        "should_stop_questioning": stop_questioning,
        "give_price_orientation_only": price_orientation_only,
        "do_not_hard_close": price_orientation_only,
        "do_not_show_checkout_card": price_orientation_only,
    }

    reasons.append(f"mode={mode} wow={wow} nba={nba['type']}")
    reasons.append(_score_summary(scores))
    reasons.append(_drivers(profile, behavior))

    return {
        "conversation_mode": mode,
        "wow_mechanism": wow,
        "roi_depth": roi_depth,
        "scores": scores,
        "question_budget": budget,
        "next_best_action": nba,
        "bot_guidance": guidance,
        "logging_reasons": reasons,
    }
