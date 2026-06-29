"""Deterministic lead-stage model for the DamiWorks website consultant.

A small state machine that decides, for a post-intake turn, what stage the lead
is in and what deterministic answer (if any) to give. It composes the existing
detectors in `web_site_intake_policy` rather than adding parallel regex logic.

The key behaviour this adds over `post_intake_response`: after the assistant
proposes a next step (e.g. "Хотите начать с Pilot / Start?") a bare affirmation
("да", "хорошо", "подходит", "давайте") advances to `contact_requested` and asks
for contact — instead of falling through to the LLM and re-qualifying.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .web_site_intake_policy import (
    IntakeContext,
    ParsedContact,
    assistant_asked_for_contact,
    contact_close_answer,
    feature_detail_answer,
    is_feature_detail,
    is_start_intent,
    parse_contact,
    post_intake_response,
    start_handoff_answer,
)


class LeadStage(str, Enum):
    recommendation_shown = "recommendation_shown"
    package_discussion = "package_discussion"
    contact_requested = "contact_requested"
    contact_collected = "contact_collected"
    closed = "closed"


@dataclass
class PostIntakeTurn:
    stage: LeadStage
    answer: str | None
    contact: ParsedContact | None = None


# Bare affirmations. Matched only when the message is short (≤3 words), is not a
# question, and starts with an affirmation token — so it never swallows
# informational sentences like "Можно начать дешевле?".
_AFFIRMATION_RE = re.compile(
    r"^(?:да|ага|угу|конечно|согласен|согласна|подходит|давай(?:те)?|"
    r"хорошо|ок|окей|ладно|норм|нормально|поехали|погнали|"
    r"го|yes|ok|sure)\b",
    re.IGNORECASE,
)


def is_affirmation(user_message: str) -> bool:
    m = (user_message or "").strip().casefold().replace("ё", "е")
    if not m or "?" in m or len(m.split()) > 3:
        return False
    return bool(_AFFIRMATION_RE.match(m))


# The assistant proposed a package / next step on its previous turn.
_PROPOSED_NEXT_STEP_RE = re.compile(
    r"хотите\s+начать|начн[её]м\s+с|двигаемся\s+дальше|готовы\s+начать|"
    r"оформляем|хотите\s+(?:оформить|подключить|запустить)|"
    r"можем\s+(?:начать|перейти\s+к\s+запуску|обсудить\s+запуск)|"
    r"перейти\s+к\s+запуску|"
    r"если\s+хотите\s+продолжить|"
    # Also fires when the bot gave a soft "next step" cue (neutral_ack_answer /
    # SOFT_NEXT_STEPS) — a user "да/хорошо" after this is a meaningful acceptance.
    r"следующим\s+шагом\s+(?:можн?о|можем)\s+перейти",
    re.IGNORECASE,
)


def assistant_proposed_next_step(last_assistant_message: str) -> bool:
    """True if the previous assistant turn proposed a package/next step or asked
    for contact — i.e. a bare 'да' is a meaningful acceptance."""
    text = last_assistant_message or ""
    if _PROPOSED_NEXT_STEP_RE.search(text):
        return True
    return assistant_asked_for_contact(text)


_CLOSED_TERMINAL_ANSWER = (
    "Заявка уже отправлена — команда свяжется с вами в WhatsApp/Telegram "
    "и уточнит детали запуска."
)


def resolve_post_intake_turn(
    user_message: str,
    ctx: IntakeContext,
    last_assistant_message: str = "",
    *,
    lead_closed: bool = False,
) -> PostIntakeTurn:
    """Decide the lead stage and deterministic answer for a post-intake turn.

    Order: closed → contact collected → (start intent OR affirmation-after-
    proposal) → other package-discussion intents → None (LLM generates).
    """
    if not ctx.exists:
        return PostIntakeTurn(LeadStage.recommendation_shown, None)

    if lead_closed:
        return PostIntakeTurn(LeadStage.closed, _CLOSED_TERMINAL_ANSWER)

    contact = parse_contact(user_message, last_assistant_message)
    if contact.kind:
        return PostIntakeTurn(
            LeadStage.contact_collected,
            contact_close_answer(user_message),
            contact,
        )

    if is_start_intent(user_message) or (
        assistant_proposed_next_step(last_assistant_message) and is_affirmation(user_message)
    ):
        return PostIntakeTurn(
            LeadStage.contact_requested,
            start_handoff_answer(last_assistant_message),
        )

    # Concrete feature mention post-intake ("квалификацию", "доставку", etc.) —
    # acknowledge and ask for contact without another discovery round.
    if is_feature_detail(user_message):
        return PostIntakeTurn(
            LeadStage.contact_requested,
            feature_detail_answer(last_assistant_message),
        )

    # Everything else (cheaper / price / implementation / not-remembered /
    # business details / informational) — reuse the existing dispatch.
    answer = post_intake_response(user_message, ctx, last_assistant_message=last_assistant_message)
    return PostIntakeTurn(LeadStage.package_discussion, answer)
