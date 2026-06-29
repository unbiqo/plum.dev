"""Domain types for the Sales Intelligence layer (project_specs.md v1.2).

These mirror the canonical session-metadata blocks (§8) and the ``strategy_result``
contract (§9.2). Runtime metadata is plain JSONB-friendly ``dict``; the ``TypedDict``
definitions here document shape and give editors/type-checkers something to lean on.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, TypedDict


class ConversationMode(str, Enum):
    """Conversation depth/style modes (§3). ``roleplay_demo`` here is the *shadow*
    classification of explicit roleplay intent on a B2B turn (before the roleplay simulation
    actually activates); the live roleplay simulation is still handled via roleplay_state
    isolation (§13)."""

    simple_explainer = "simple_explainer"
    microbusiness_helper = "microbusiness_helper"
    light_roi_diagnostic = "light_roi_diagnostic"
    full_roi_audit = "full_roi_audit"
    integration_discovery = "integration_discovery"
    roleplay_demo = "roleplay_demo"
    low_fit_nurture = "low_fit_nurture"


class WowMechanism(str, Enum):
    """Supported wow mechanisms (§4.1) — the way we create the wow effect this turn."""

    simple_explanation = "simple_explanation"
    roleplay_demo = "roleplay_demo"
    microbusiness_assistant_pitch = "microbusiness_assistant_pitch"
    light_roi_audit = "light_roi_audit"
    full_roi_audit = "full_roi_audit"
    integration_architecture_map = "integration_architecture_map"
    checkout_or_call = "checkout_or_call"
    nurture = "nurture"


class NextBestActionType(str, Enum):
    """Next-best-action types (§11.4)."""

    answer_only = "answer_only"
    ask_simple_context_question = "ask_simple_context_question"
    ask_business_context = "ask_business_context"
    ask_metric_for_roi = "ask_metric_for_roi"
    give_value = "give_value"
    offer_roleplay = "offer_roleplay"
    offer_light_roi = "offer_light_roi"
    offer_full_roi = "offer_full_roi"
    offer_integration_discovery = "offer_integration_discovery"
    price_orientation = "price_orientation"
    offer_call_or_specification = "offer_call_or_specification"
    simplify = "simplify"
    nurture = "nurture"


# Allowed extraction provenance for a wrapped field value (§8.2).
ExtractionType = Literal["explicit", "inferred", "default", "unknown"]

# Allowed ROI depth (§8.6).
RoiDepth = Literal["none", "rough_estimate", "light_roi", "full_roi"]

# Canonical score keys (§11.1). Order matters for stable serialization.
SCORE_KEYS: tuple[str, ...] = (
    "icp_fit_score",
    "roi_potential_score",
    "operational_pain_score",
    "data_readiness_score",
    "conversation_friction_score",
    "buying_readiness_score",
    "ai_fit_score",
    "integration_complexity_score",
)


class FieldValue(TypedDict):
    """Wrapped extracted business value (§8.2)."""

    value: Any
    confidence: float
    source_text: str | None
    extraction_type: ExtractionType
    last_updated_at: str | None
    conflict: bool
    conflict_notes: list[str]


class Scores(TypedDict):
    icp_fit_score: int
    roi_potential_score: int
    operational_pain_score: int
    data_readiness_score: int
    conversation_friction_score: int
    buying_readiness_score: int
    ai_fit_score: int
    integration_complexity_score: int


class QuestionBudget(TypedDict):
    max_questions_before_value: int
    qualification_questions_asked_since_last_value: int
    remaining_questions_before_value: int


class NextBestAction(TypedDict):
    type: str
    value_message: str | None
    question: str | None
    target_field: str | None
    should_ask_now: bool


class BotGuidance(TypedDict):
    tone: str
    avoid_topics: list[str]
    recommended_angle: str
    should_offer_roi_audit: bool
    should_offer_roleplay: bool
    should_offer_call: bool
    should_simplify: bool
    should_stop_questioning: bool
    # Price-first guardrails: a bare price request must not trigger a hard close or checkout
    # card, and must not turn into a questionnaire.
    give_price_orientation_only: bool
    do_not_hard_close: bool
    do_not_show_checkout_card: bool


class ROIScenario(TypedDict):
    lost_revenue: float | None
    lost_margin_profit: float | None
    recoverable_margin_profit: float | None
    time_savings_value: float | None
    monthly_net_effect: float | None
    payback_period_months: float | None
    roi_percentage: float | None
    notes: list[str]


class ROIResult(TypedDict):
    """Deterministic ROI computation result (§12.10). All math is Python — never LLM."""

    roi_depth: str  # none | rough_estimate | light_roi | full_roi
    can_show_to_user: bool
    calculation_confidence: str  # low | medium | high
    confidence_reasons: list[str]
    scenarios: dict[str, ROIScenario]
    assumptions: list[str]
    missing_fields: list[str]
    warnings: list[str]
    user_safe_summary: str
    next_field_for_better_accuracy: str | None
    should_ask_for_metric: bool
    metric_to_ask_next: str | None
    computed_at: str | None
    source_fields: list[str]


class StrategyResult(TypedDict):
    """Output of the strategy engine + wow router (§9.2)."""

    conversation_mode: str
    wow_mechanism: str
    roi_depth: str
    scores: Scores
    question_budget: QuestionBudget
    next_best_action: NextBestAction
    bot_guidance: BotGuidance
    logging_reasons: list[str]
