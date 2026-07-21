"""E2E: a demo visitor books through the real medical orchestrator with a
BookingProvider wired in. Drives handle_medical_center_chat turn by turn and
asserts the demo_appointments row is confirmed and the ready lead is formed.

Fake planner (no real LLM); in-memory store + fixed clock (no live DB).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from app.booking_provider import DemoBookingProvider, InMemoryAppointmentStore
from app.demo_seed import seed_demo_appointments
from app.medical_center_demo import MEDICAL_CENTER_INSTANCE_ID, handle_medical_center_chat
from app.schemas import ChatHistoryMessage, ChatRequest

# Tue 2026-07-21 08:00 Almaty (03:00 UTC) — офтальмолог Панченко works Tue.
_CLOCK = datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc)

_BOOKING_PLAN = {
    "current_intent": "wants_booking", "intent_priority": "high",
    "should_pause_qualification": False, "user_frustration": False, "correction": False,
    "question_to_answer": "", "response_goal": "", "must_mention": [], "must_not_repeat": [],
    "recommended_next_step": "none", "do_not_ask": [], "handoff_recommended": False,
    "reason": "t", "slots": {"specialty": "офтальмолог"},
}


class _FakeGemini:
    class settings:
        general_model = "m"
        general_model_pool = ("m",)

    def __init__(self, plan: dict) -> None:
        self._plan = plan

    async def _generate_text(self, **kw):
        if kw.get("response_mime_type") == "application/json":
            return json.dumps(self._plan)
        return "ok"

    def _format_chat_prompt(self, message, history, client_facts=None, history_limit=None):
        return f"USER: {message}"


def _provider() -> DemoBookingProvider:
    return DemoBookingProvider(InMemoryAppointmentStore(), clock=lambda: _CLOCK)


class _Session:
    def __init__(self, provider: DemoBookingProvider, plan: dict = _BOOKING_PLAN) -> None:
        self.provider = provider
        self.gemini = _FakeGemini(plan)
        self.history: list[ChatHistoryMessage] = []

    def say(self, message: str):
        req = ChatRequest(
            channel="web_site", chat_id="e2e", instance_id=MEDICAL_CENTER_INSTANCE_ID,
            message=message, chat_history=list(self.history),
        )
        resp = asyncio.run(handle_medical_center_chat(self.gemini, req, provider=self.provider))
        self.history.append(ChatHistoryMessage(role="user", content=message))
        self.history.append(ChatHistoryMessage(role="assistant", content=resp.answer))
        return resp


def _confirmed_rows(provider: DemoBookingProvider) -> list:
    store = provider._store  # type: ignore[attr-defined]
    return [r for r in store._rows.values() if r.status == "confirmed"]


# ---------------------------------------------------------------------------
# Branch 1: "хочу к офтальмологу" → doctor + windows → pick → confirm
# ---------------------------------------------------------------------------

def test_e2e_book_by_specialty() -> None:
    provider = _provider()
    session = _Session(provider)

    offer = session.say("хочу записаться к офтальмологу")
    assert offer.metadata["booking_provider_used"] is True
    assert offer.metadata["conversation_status"] == "slots_offered"
    assert "Панченко" in offer.answer  # the specialty's doctor
    assert "09:00" in offer.answer     # a real window from the schedule

    picked = session.say("запишите на сегодня 09:00")
    assert picked.metadata["conversation_status"] == "awaiting_contact"

    done = session.say("Дамир, 23 года, +7 700 111 22 33")
    assert done.metadata["conversation_status"] == "booking_created"
    assert done.lead_status == "contact_collected"

    # demo_appointments row confirmed + ready lead formed.
    appt = done.metadata["demo_appointment"]
    assert appt is not None
    assert appt["status"] == "confirmed"
    assert appt["doctor_name"] == "Ольга Панченко"
    assert appt["patient_name"] == "Дамир"
    assert appt["start_ts"] == "2026-07-21T09:00:00+05:00"

    rows = _confirmed_rows(provider)
    assert len(rows) == 1 and rows[0].doctor_id == "ольга_панченко"


def test_e2e_booked_slot_no_longer_offered() -> None:
    provider = _provider()
    session = _Session(provider)
    session.say("хочу записаться к офтальмологу")
    session.say("запишите на сегодня 09:00")
    session.say("Дамир, 23 года, +7 700 111 22 33")

    # A second visitor asking for the same specialty must not be offered 09:00.
    other = _Session(provider)
    offer2 = other.say("хочу к офтальмологу")
    assert "09:00" not in offer2.answer
    assert "09:30" in offer2.answer  # next window is still free


# ---------------------------------------------------------------------------
# Branch 2: "к конкретному врачу"
# ---------------------------------------------------------------------------

def test_e2e_book_by_named_doctor() -> None:
    provider = _provider()
    # Planner without a specialty slot: the doctor name in the message drives it.
    plan = {**_BOOKING_PLAN, "slots": {}}
    session = _Session(provider, plan)

    offer = session.say("хочу записаться к Панченко")
    assert offer.metadata["booking_provider_used"] is True
    assert "Панченко" in offer.answer
    assert offer.metadata["conversation_status"] == "slots_offered"

    session.say("давайте сегодня 10:00")
    done = session.say("Айгуль, 30 лет, +7 701 222 33 44")
    assert done.metadata["conversation_status"] == "booking_created"
    appt = done.metadata["demo_appointment"]
    assert appt["doctor_id"] == "ольга_панченко"
    assert appt["start_ts"] == "2026-07-21T10:00:00+05:00"


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def test_seed_is_deterministic_and_reduces_availability() -> None:
    provider = _provider()
    first = seed_demo_appointments(provider, MEDICAL_CENTER_INSTANCE_ID)
    assert first == 7  # every other of the 13 KB doctors (indices 0,2,…,12)
    assert len(_confirmed_rows(provider)) == 7

    provider.reset(MEDICAL_CENTER_INSTANCE_ID)
    assert _confirmed_rows(provider) == []
    # Deterministic (no RNG): from a clean store the same count books again.
    assert seed_demo_appointments(provider, MEDICAL_CENTER_INSTANCE_ID) == first


# ---------------------------------------------------------------------------
# Without a provider, the legacy flow still runs (provider path is inert)
# ---------------------------------------------------------------------------

def test_no_provider_uses_legacy_booking_flow() -> None:
    session_gemini = _FakeGemini(_BOOKING_PLAN)
    req = ChatRequest(
        channel="web_site", chat_id="legacy", instance_id=MEDICAL_CENTER_INSTANCE_ID,
        message="хочу записаться к офтальмологу", chat_history=[],
    )
    resp = asyncio.run(handle_medical_center_chat(session_gemini, req))  # no provider
    assert not resp.metadata.get("booking_provider_used")
