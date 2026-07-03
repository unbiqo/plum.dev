"""Tests for the Calendly-preferred contact ask (ChatRequest.calendly_enabled).

When the frontend reports a visible Calendly booking CTA, contact asks present
booking a call as the preferred next step; otherwise the legacy asks are used.
The Calendly ask must never leak prices and must keep the contact-collection
state machine working (bare name / phone parsed on the next turn).
"""
from __future__ import annotations

import re

from app.web_site_intake_policy import (
    CALENDLY_CONTACT_ASK,
    IntakeContext,
    answer_has_contact_ask,
    assistant_asked_for_contact,
    parse_contact,
    pick_contact_ask,
)
from app.web_site_lead import LeadStage, resolve_post_intake_turn


def _ctx() -> IntakeContext:
    return IntakeContext(
        exists=True,
        channels=["WhatsApp"],
        tasks=["Отвечать на вопросы"],
        recommended_package="Sales Assistant",
    )


def test_start_intent_uses_calendly_ask_when_enabled():
    turn = resolve_post_intake_turn("хочу начать", _ctx(), "", calendly_enabled=True)
    assert turn.stage == LeadStage.contact_requested
    assert CALENDLY_CONTACT_ASK in (turn.answer or "")


def test_start_intent_keeps_legacy_ask_when_disabled():
    turn = resolve_post_intake_turn("хочу начать", _ctx(), "")
    assert turn.stage == LeadStage.contact_requested
    assert turn.answer
    assert CALENDLY_CONTACT_ASK not in turn.answer


def test_calendly_ask_has_no_prices_and_no_guarantees():
    assert "₸" not in CALENDLY_CONTACT_ASK
    assert not re.search(r"\d{3}", CALENDLY_CONTACT_ASK)
    assert "гарант" not in CALENDLY_CONTACT_ASK.casefold()


def test_calendly_ask_counts_as_contact_ask():
    assert answer_has_contact_ask(CALENDLY_CONTACT_ASK)
    assert assistant_asked_for_contact(CALENDLY_CONTACT_ASK)


def test_contact_still_collected_after_calendly_ask():
    # Bare name right after the Calendly ask is still a contact reply.
    assert parse_contact("Дамир", CALENDLY_CONTACT_ASK).kind == "name"
    # Phone closes the lead as before.
    turn = resolve_post_intake_turn(
        "+7 707 123 45 67", _ctx(), CALENDLY_CONTACT_ASK, calendly_enabled=True
    )
    assert turn.stage == LeadStage.contact_collected


def test_calendly_ask_not_repeated_back_to_back():
    ask = pick_contact_ask(CALENDLY_CONTACT_ASK, calendly_enabled=True)
    assert ask != CALENDLY_CONTACT_ASK
