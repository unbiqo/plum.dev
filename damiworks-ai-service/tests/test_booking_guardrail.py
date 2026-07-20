"""Tests for the booking slot guardrail (app/booking_guardrail.py).

Rule under test: the model may only speak slots supplied by the slot provider
(deterministic demo source today, SoM API tomorrow). Invented dates/times —
or any concrete slot when the provider supplied none — must be replaced with
the safe "уточню и вернусь" answer.
"""

from __future__ import annotations

from app.booking_guardrail import (
    SAFE_NO_SLOTS_ANSWER,
    enforce_slot_guardrail,
    parse_slot_label,
)

OFFERED = ["завтра 10:00", "завтра 15:30", "послезавтра 11:00"]


# ---------------------------------------------------------------------------
# parse_slot_label
# ---------------------------------------------------------------------------

def test_parse_slot_label_ok() -> None:
    assert parse_slot_label("завтра 10:00") == ("завтра", "10:00")
    assert parse_slot_label("послезавтра 9:30") == ("послезавтра", "09:30")


def test_parse_slot_label_rejects_garbage() -> None:
    assert parse_slot_label("") is None
    assert parse_slot_label("скоро") is None
    assert parse_slot_label("10:00") is None


# ---------------------------------------------------------------------------
# Pass-through cases
# ---------------------------------------------------------------------------

def test_answer_using_offered_slot_passes() -> None:
    answer = "Есть окно завтра в 10:00.\n\nУдобно будет?"
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=True,
    )
    assert replaced is False
    assert result == answer


def test_answer_without_any_time_mentions_passes() -> None:
    answer = "Могу показать ближайшие окна к терапевту.\n\nПоказать?"
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=True,
    )
    assert replaced is False
    assert result == answer


def test_confirmed_slot_restated_passes() -> None:
    # The caller includes the already-confirmed slot in offered_slots.
    answer = "Вы записаны на послезавтра 11:00 к терапевту."
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=False,
    )
    assert replaced is False
    assert result == answer


def test_working_hours_are_not_slot_claims() -> None:
    answer = "Клиника работает с 9:00 до 18:00 без выходных."
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=[], booking_context=True,
    )
    assert replaced is False
    assert result == answer


def test_bare_time_outside_booking_context_is_tolerated() -> None:
    answer = "Приём обычно длится до 16:00."
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=False,
    )
    assert replaced is False
    assert result == answer


# ---------------------------------------------------------------------------
# Replacement cases
# ---------------------------------------------------------------------------

def test_invented_day_time_pair_is_replaced() -> None:
    answer = "Записал вас на завтра в 12:00.\n\nЖдём вас!"
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=False,
    )
    assert replaced is True
    assert result == SAFE_NO_SLOTS_ANSWER


def test_invented_slot_on_unlisted_day_is_replaced() -> None:
    answer = "Могу предложить сегодня в 18:00."
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=False,
    )
    assert replaced is True
    assert result == SAFE_NO_SLOTS_ANSWER


def test_bare_time_in_booking_context_is_replaced() -> None:
    answer = "Есть свободное окно в 14:00, записать?"
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=OFFERED, booking_context=True,
    )
    assert replaced is True
    assert result == SAFE_NO_SLOTS_ANSWER


def test_no_slots_from_provider_means_safe_answer() -> None:
    # The provider returned nothing: the model has no right to name any time.
    answer = "Могу записать вас завтра в 10:00."
    result, replaced = enforce_slot_guardrail(
        answer=answer, offered_slots=[], booking_context=True,
    )
    assert replaced is True
    assert result == SAFE_NO_SLOTS_ANSWER
    assert "уточню" in result.lower()


def test_empty_or_blank_answer_is_untouched() -> None:
    assert enforce_slot_guardrail(
        answer="", offered_slots=OFFERED, booking_context=True,
    ) == ("", False)
    assert enforce_slot_guardrail(
        answer="   ", offered_slots=OFFERED, booking_context=True,
    ) == ("   ", False)


def test_guardrail_never_raises_on_garbage_slots() -> None:
    result, replaced = enforce_slot_guardrail(
        answer="Окно завтра в 10:00 подойдёт?",
        offered_slots=["не слот", "", "??"],
        booking_context=True,
    )
    # No parseable provider slots -> the day+time claim is a violation.
    assert replaced is True
    assert result == SAFE_NO_SLOTS_ANSWER


# ---------------------------------------------------------------------------
# End-to-end: the replaced answer is what the client gets AND what is logged
# ---------------------------------------------------------------------------

def test_replaced_answer_is_final_response() -> None:
    """handle_medical_center_chat returns the guardrail-safe text, not the raw
    writer output. The writer's answer here passes the medical validate_answer
    checks (no availability-claim phrasing), so only the slot guardrail can
    catch the invented "завтра в 15:00" (the demo provider offers other times).
    """
    from tests.test_medical_center_demo import (
        FakeGemini,
        _default_planner,
        _request,
        _run,
    )
    from app.medical_center_demo import handle_medical_center_chat

    gem = FakeGemini(
        planner=_default_planner(current_intent="wants_booking"),
        writer_texts=["Подскажите, удобно ли вам завтра в 15:00?"],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Можно сегодня к неврологу?")))
    assert gem.writer_calls == 1  # validate_answer passed — no repair pass
    assert resp.answer == SAFE_NO_SLOTS_ANSWER


def test_replaced_answer_is_what_gets_logged_to_history() -> None:
    """History invariant: ai_conversation_messages must store the final text
    the client actually received. The /chat endpoint logs ``response.answer``
    after the demo handler ran the guardrail, so the logged assistant_answer
    must be the safe replacement, never the writer's invented slot.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import api
    from app.medical_center_demo import MEDICAL_CENTER_INSTANCE_ID
    from tests.test_medical_center_demo import FakeGemini, _default_planner

    logged: dict = {}

    class _FakeSupabase:
        async def log_ai_conversation_turn(self, **kwargs) -> None:
            logged.update(kwargs)

    gem = FakeGemini(
        planner=_default_planner(current_intent="wants_booking"),
        writer_texts=["Подскажите, удобно ли вам завтра в 15:00?"],
    )
    app = FastAPI()
    app.include_router(api.router)
    app.state.gemini = gem
    app.state.supabase = _FakeSupabase()

    response = TestClient(app).post(
        "/api/v1/chat",
        json={
            "channel": "web_site",
            "chat_id": "med-guardrail-1",
            "instance_id": MEDICAL_CENTER_INSTANCE_ID,
            "message": "Можно сегодня к неврологу?",
            "chat_history": [],
        },
    )
    assert response.status_code == 200
    answer = response.json()["answer"]
    assert answer == SAFE_NO_SLOTS_ANSWER
    # The same final text went to the conversation log (history for next turns).
    assert logged.get("assistant_answer") == answer
