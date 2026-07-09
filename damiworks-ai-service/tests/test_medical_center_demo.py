"""Unit tests for the Medical Center demo agent (MedNova Clinic).

These run without any API key — the Gemini service is stubbed (``FakeGemini``).
They assert: emergency short-circuit (deterministic, pre-LLM), medical safety
guardrails (no diagnosis / prescription / lab interpretation / slot promises /
child contact / invented doctors & prices), lead lifecycle, metadata, and
no-crash behavior.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.medical_center_demo import (
    INVALID_CONTACT_ANSWER,
    MEDICAL_CENTER_INSTANCE_ID,
    handle_medical_center_chat,
)
from app.medical_center_guardrails import (
    EMERGENCY_ANSWER,
    build_safe_fallback,
    kb_doctor_names,
    kb_price_set,
    validate_answer,
)
from app.medical_center_kb import get_full_kb_context
from app.medical_center_slots import normalize_symptom_terms, resolve_slot
from app.medical_center_planner import (
    reclassify_discount_question,
    reclassify_medical_advice_question,
)
from app.medical_center_state import (
    ConversationState,
    apply_planner_updates,
    build_conversation_state,
    classify_contact,
    detect_red_flags,
    detect_symptom_specialty,
    extract_contact,
    looks_like_contact,
    looks_like_invalid_phone,
)
from app.medical_center_writer import build_turn_plan
from app.schemas import ChatHistoryMessage, ChatRequest


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _Settings:
    general_model = "fake-model"
    general_model_pool = ("fake-model",)


class FakeGemini:
    """Stub that returns queued planner JSON / writer text instead of calling Gemini."""

    def __init__(self, planner: dict | None = None, writer_texts=None, fail_planner=False):
        self.settings = _Settings()
        self._planner_raw = None if fail_planner else json.dumps(planner or _default_planner())
        self._writer_texts = list(writer_texts or [])
        self.planner_calls = 0
        self.writer_calls = 0

    async def _generate_text(self, **kw):
        if kw.get("response_mime_type") == "application/json":
            self.planner_calls += 1
            if self._planner_raw is None:
                raise RuntimeError("planner LLM down")
            return self._planner_raw
        self.writer_calls += 1
        if not self._writer_texts:
            raise RuntimeError("writer LLM down")
        return self._writer_texts.pop(0)

    def _format_chat_prompt(self, message, history, client_facts=None):
        return f"USER: {message}"


def _default_planner(**overrides) -> dict:
    plan = {
        "current_intent": "answer_question",
        "intent_priority": "high",
        "answers_previous_question": False,
        "user_shifted_topic": False,
        "should_pause_qualification": True,
        "user_frustration": False,
        "correction": False,
        "question_to_answer": "вопрос",
        "response_goal": "ответить",
        "must_mention": [],
        "must_not_repeat": [],
        "recommended_next_step": "none",
        "do_not_ask": [],
        "handoff_recommended": False,
        "reason": "test",
        "slots": {},
    }
    plan.update(overrides)
    return plan


def _msg(role: str, content: str) -> ChatHistoryMessage:
    return ChatHistoryMessage(role=role, content=content)


def _request(message: str, history=None) -> ChatRequest:
    return ChatRequest(
        channel="web_site",
        chat_id="med1",
        instance_id=MEDICAL_CENTER_INSTANCE_ID,
        message=message,
        chat_history=history or [],
    )


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# KB facts
# ---------------------------------------------------------------------------

def test_instance_id() -> None:
    assert MEDICAL_CENTER_INSTANCE_ID == "damiworks_medical_center_demo"


def test_kb_contains_cardiologist_and_ecg_prices() -> None:
    kb = get_full_kb_context()
    assert "16 000" in kb  # кардиолог первичный приём
    assert "6 000" in kb   # ЭКГ с расшифровкой


def test_kb_price_set_is_exact() -> None:
    assert kb_price_set() == frozenset({
        1500, 2500, 3500, 6000, 8000, 9000, 10000, 10500, 11000, 11500,
        12000, 13000, 13500, 14000, 14500, 15000, 15500, 16000, 18000,
        20000, 29000, 30000, 32000, 45000, 65000,
    })


def test_kb_has_no_damiworks_branding() -> None:
    assert "damiworks" not in get_full_kb_context().casefold()


def test_kb_doctor_names_parsed() -> None:
    names = kb_doctor_names()
    for expected in ("Ким", "Омарова", "Рахимов", "Ахметов", "Панченко", "Сарсенова"):
        assert expected in names
    assert "Иванов" not in names


def test_kb_contains_dentist() -> None:
    kb = get_full_kb_context()
    assert "стоматолог" in kb.casefold()
    assert "Сарсенова" in kb
    assert "6 000" in kb  # dentist exam/consultation
    assert "18 000" in kb  # cavity filling
    assert "65 000" in kb  # crown


# ---------------------------------------------------------------------------
# Red-flag detector
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "Сильная давящая боль в груди, трудно дышать",
        "У бабушки перекосило лицо и невнятная речь",
        "Ребенок вялый, трудно разбудить",
        "У жены начались судороги",
        "Сильное кровотечение, кровь не останавливается",
        "Беременна, началось кровотечение и сильная боль в животе",
        "После укуса осы отек горла, задыхаюсь",
        "Температура у младенца, ему 2 месяца",
        "Муж потерял сознание сегодня утром",
    ],
)
def test_red_flag_detected(message: str) -> None:
    assert detect_red_flags(message) is not None, message


@pytest.mark.parametrize(
    "message",
    [
        "Иногда побаливает в груди при нагрузке, сколько стоит приём кардиолога?",
        "Сколько стоит кардиолог?",
        "Хочу записать ребенка к педиатру, ему 5 лет, кашель",
        "Болит горло и ухо, к кому записаться?",
        "У меня температура 37.5 и насморк",
    ],
)
def test_routine_symptoms_not_red_flag(message: str) -> None:
    assert detect_red_flags(message) is None, message


def test_red_flag_preempts_llm() -> None:
    gem = FakeGemini()
    resp = _run(handle_medical_center_chat(gem, _request("Сильная боль в груди и трудно дышать")))
    assert resp.answer == EMERGENCY_ANSWER
    assert gem.planner_calls == 0 and gem.writer_calls == 0
    assert "103/112" in resp.answer
    assert "запис" not in resp.answer.casefold()
    md = resp.metadata
    assert md["emergency_short_circuit"] is True
    assert md["state"]["urgency_flag"] == "emergency"
    assert md["conversation_status"] == "emergency"
    assert md["conversation_status_label"] == "Срочная помощь"


def test_routine_chest_question_goes_through_normal_pipeline() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price"),
        writer_texts=["Первичный приём кардиолога — 16 000 ₸, ЭКГ с расшифровкой — 6 000 ₸."],
    )
    resp = _run(handle_medical_center_chat(
        gem, _request("Иногда побаливает в груди при нагрузке, сколько стоит приём кардиолога?")
    ))
    assert gem.planner_calls == 1 and gem.writer_calls == 1
    assert "16 000" in resp.answer
    assert resp.metadata["validation_result"]["failed"] is False


def test_emergency_sticky_but_planned_booking_still_works() -> None:
    # Red flag earlier in history; the follow-up is a calm planned booking.
    history = [
        _msg("user", "У отца сильная боль в груди и трудно дышать"),
        _msg("assistant", EMERGENCY_ANSWER),
    ]
    gem = FakeGemini(
        planner=_default_planner(current_intent="contact"),
        writer_texts=[
            "Спасибо! Передам заявку администратору — он свяжется и подтвердит удобное время.",
        ],
    )
    resp = _run(handle_medical_center_chat(gem, _request(
        "Спасибо, ему уже лучше. Хочу записаться к кардиологу планово, +7 701 111 22 33",
        history=history,
    )))
    assert gem.writer_calls == 1  # normal pipeline, not short-circuited
    assert resp.lead_status == "contact_collected"
    assert resp.metadata["state"]["urgency_flag"] == "emergency"  # sticky for the lead
    assert resp.metadata["medical_lead_status"] == "appointment_requested"


# ---------------------------------------------------------------------------
# Guardrails: prices, diagnosis, prescription, labs, slots, child contact
# ---------------------------------------------------------------------------

def test_guardrail_rejects_invented_price() -> None:
    res = validate_answer("МРТ стоит 25 000 ₸.", ConversationState(), _default_planner())
    assert res.failed and not res.checks["no_invented_prices"]


def test_guardrail_accepts_kb_prices() -> None:
    res = validate_answer(
        "Первичный приём кардиолога — 16 000 ₸, ЭКГ — 6 000 ₸.",
        ConversationState(),
        _default_planner(current_intent="ask_price"),
    )
    assert not res.failed, res.fix


def test_guardrail_rejects_diagnosis() -> None:
    for answer in (
        "Похоже, у вас гастрит.",
        "Скорее всего, это мигрень.",
        "У вас бронхит, ничего страшного.",
    ):
        res = validate_answer(answer, ConversationState(), _default_planner())
        assert res.failed and not res.checks["no_diagnosis"], answer


def test_guardrail_allows_specialty_routing() -> None:
    res = validate_answer(
        "С такими жалобами обычно записывают к ЛОР-врачу. Могу помочь с записью.",
        ConversationState(),
        _default_planner(current_intent="ask_specialty_advice"),
    )
    assert res.checks["no_diagnosis"] is True
    assert not res.failed, res.fix


def test_guardrail_rejects_prescription() -> None:
    for answer in (
        "Примите ибупрофен 400 мг три раза в день.",
        "Пейте антибиотик широкого спектра.",
        "Рекомендую принимать парацетамол на ночь.",
    ):
        res = validate_answer(answer, ConversationState(), _default_planner())
        assert res.failed and not res.checks["no_prescription"], answer


def test_guardrail_accepts_prescription_refusal() -> None:
    res = validate_answer(
        "Лекарства назначает врач после осмотра. Могу подсказать, к какому специалисту обратиться.",
        ConversationState(),
        _default_planner(current_intent="medical_advice_request"),
    )
    assert res.checks["no_prescription"] is True
    assert not res.failed, res.fix


def test_guardrail_rejects_lab_interpretation() -> None:
    res = validate_answer(
        "Ваши анализы показывают воспаление, это выше нормы.",
        ConversationState(),
        _default_planner(),
    )
    assert res.failed and not res.checks["no_lab_interpretation"]


def test_guardrail_rejects_slot_promise() -> None:
    res = validate_answer(
        "Записал вас на 15:00 к кардиологу, ждём вас завтра в клинике.",
        ConversationState(),
        _default_planner(current_intent="wants_booking"),
    )
    assert res.failed and not res.checks["no_invented_availability"]

    res2 = validate_answer(
        "Передам заявку — администратор свяжется и подтвердит ближайшее доступное время.",
        ConversationState(),
        _default_planner(current_intent="wants_booking"),
    )
    assert res2.checks["no_invented_availability"] is True


def test_guardrail_rejects_child_contact_request() -> None:
    for answer in (
        "Оставьте, пожалуйста, номер ребёнка для связи.",
        "Мне понадобится его номер телефона.",
        "Продиктуйте телефон сына.",
    ):
        res = validate_answer(answer, ConversationState(), _default_planner())
        assert res.failed and not res.checks["no_child_contact_request"], answer


def test_guardrail_accepts_adult_contact_request() -> None:
    res = validate_answer(
        "Оставьте, пожалуйста, ваше имя и WhatsApp/телефон для связи.",
        ConversationState(),
        _default_planner(current_intent="wants_booking"),
    )
    assert res.checks["no_child_contact_request"] is True
    assert not res.failed, res.fix


def test_guardrail_rejects_invented_doctor() -> None:
    res = validate_answer(
        "Вас примет доктор Иванов, он отличный специалист.",
        ConversationState(),
        _default_planner(),
    )
    assert res.failed and not res.checks["no_invented_doctor"]


def test_guardrail_accepts_kb_doctor_with_declension() -> None:
    res = validate_answer(
        "Детей принимает врач Мадина Омарова. Можно записаться к врачу Руслану Киму.",
        ConversationState(),
        _default_planner(current_intent="ask_doctor"),
    )
    assert res.checks["no_invented_doctor"] is True
    assert not res.failed, res.fix


def test_guardrail_rejects_invented_promotion() -> None:
    for answer in (
        "Могу предложить рассрочку на 3 месяца.",
        "Сделаем скидку 20% на первый визит.",
    ):
        res = validate_answer(answer, ConversationState(), _default_planner())
        assert res.failed and not res.checks["no_invented_promotion"], answer


def test_guardrail_accepts_kb_discounts() -> None:
    res = validate_answer(
        "Пенсионерам скидка 10% на консультации по будням до 13:00, семейная карта даёт 5% на консультации.",
        ConversationState(),
        _default_planner(current_intent="ask_discount"),
    )
    assert res.checks["no_invented_promotion"] is True
    assert not res.failed, res.fix


def test_guardrail_rejects_guarantee() -> None:
    res = validate_answer(
        "Гарантируем полное выздоровление после курса.",
        ConversationState(),
        _default_planner(),
    )
    assert res.failed and not res.checks["no_guarantees"]


def test_price_question_allows_honest_admin_handoff() -> None:
    # Service not priced in KB — an honest handoff must NOT trigger the
    # price-present repair loop.
    res = validate_answer(
        "Такой услуги нет в моей базе — точную стоимость уточнит администратор.",
        ConversationState(),
        _default_planner(current_intent="ask_price"),
    )
    assert res.checks["price_present_when_asked"] is True
    assert not res.failed, res.fix


def test_doctor_schedule_answer_passes() -> None:
    res = validate_answer(
        "Кардиолог Руслан Ким принимает во вторник и четверг с 14:00 до 20:00, в субботу с 10:00 до 14:00. "
        "Точное свободное время подтвердит администратор.",
        ConversationState(),
        _default_planner(current_intent="ask_schedule"),
    )
    assert not res.failed, res.fix


def test_no_booking_cta_in_emergency_context() -> None:
    state = ConversationState(urgency_flag="emergency")
    res = validate_answer(
        "Рекомендую записаться к кардиологу, могу оформить запись.",
        state,
        _default_planner(current_intent="symptom_description"),
    )
    assert res.failed and not res.checks["no_booking_cta_on_emergency"]


def test_guardrail_rejects_repeated_greeting() -> None:
    state = ConversationState(greeting_already_sent=True)
    res = validate_answer(
        "Здравствуйте! Приём терапевта стоит 12 000 ₸.",
        state,
        _default_planner(current_intent="ask_price"),
    )
    assert res.failed and not res.checks["no_repeated_greeting"]


def test_guardrail_rejects_reasking_known_slot() -> None:
    state = ConversationState(age="5")
    res = validate_answer(
        "Хорошо. Подскажите, сколько лет пациенту?",
        state,
        _default_planner(),
    )
    assert res.failed and not res.checks["no_repeated_known_slot"]


# ---------------------------------------------------------------------------
# Orchestrator: repair flow and safety
# ---------------------------------------------------------------------------

def test_orchestrator_repairs_prescription() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="medical_advice_request"),
        writer_texts=[
            "Примите ибупрофен 400 мг.",  # prescription → fails
            "Лекарства назначает врач после осмотра. Могу подсказать, к какому специалисту обратиться.",
        ],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Назначьте мне антибиотик")))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True
    assert "ибупрофен" not in resp.answer.casefold()
    assert "мг" not in resp.answer.casefold()


def test_orchestrator_repairs_diagnosis() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="symptom_description"),
        writer_texts=[
            "Похоже, у вас гастрит.",  # diagnosis → fails
            "Оценить это может врач на приёме — с такими жалобами обычно идут к гастроэнтерологу.",
        ],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Изжога и боль в животе после еды")))
    assert gem.writer_calls == 2
    assert "гастрит" not in resp.answer.casefold()


def test_orchestrator_repairs_slot_promise() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="wants_booking"),
        writer_texts=[
            "Записал вас на 15:00 к неврологу!",  # slot promise → fails
            "Передам заявку — администратор свяжется и подтвердит ближайшее доступное время.",
        ],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Можно сегодня к неврологу?")))
    assert gem.writer_calls == 2
    assert "15:00" not in resp.answer


def test_orchestrator_repairs_child_contact_wording() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="wants_booking", recommended_next_step="ask_contact"),
        writer_texts=[
            "Для записи мне нужен номер ребёнка.",  # child contact → fails
            "Оставьте, пожалуйста, ваше имя и WhatsApp/телефон для связи.",
        ],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Хочу записать сына, ему 5 лет, кашель")))
    assert gem.writer_calls == 2
    low = resp.answer.casefold()
    assert "номер ребёнка" not in low and "номер ребенка" not in low
    assert "ваше имя" in low


def test_missing_price_never_hallucinated() -> None:
    # Writer keeps inventing a non-KB price → deterministic safe fallback, no ₸.
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price"),
        writer_texts=[
            "МРТ головного мозга стоит 25 000 ₸.",
            "МРТ обойдётся примерно в 25 000 ₸.",
        ],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Сколько стоит МРТ?")))
    assert "₸" not in resp.answer
    assert "25 000" not in resp.answer
    assert "администратор" in resp.answer.casefold()


def test_contact_collection_sets_lead_status() -> None:
    # A cold booking request with a contact but no slot yet must offer slots
    # first (slots-before-contact flow), while retaining the collected contact.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="contact",
            slots={"specialty": "кардиолог", "contact": "+7 701 222 33 44"},
        ),
    )
    resp = _run(handle_medical_center_chat(
        gem, _request("Хочу записаться к кардиологу, мой номер +7 701 222 33 44")
    ))
    assert resp.metadata["conversation_status"] == "slots_offered"
    assert "демо-окна" in resp.answer.casefold()
    assert resp.lead_status == "contact_collected"  # contact already on file
    assert resp.metadata["state"]["contact"]
    assert resp.metadata["booking_stage"] == "slots_offered"


def test_metadata_carries_medical_state() -> None:
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="symptom_description",
            slots={
                "specialty": "педиатр",
                "age": "5",
                "symptoms_or_goal": "температура и кашель",
                "patient_name": "Алишер",
            },
        ),
        writer_texts=["Для ребёнка подойдёт педиатр. Подсказать удобное время?"],
    )
    resp = _run(handle_medical_center_chat(gem, _request("Сыну 5 лет, температура и кашель")))
    state = resp.metadata["state"]
    assert state["specialty"] == "педиатр"
    assert state["age"] == "5"
    assert state["symptoms_or_goal"] == "температура и кашель"
    assert state["urgency_flag"] == "normal"


def test_orchestrator_never_crashes_on_writer_failure() -> None:
    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"), writer_texts=[])
    resp = _run(handle_medical_center_chat(gem, _request("сколько стоит терапевт?")))
    assert resp.answer
    assert resp.metadata.get("error")
    assert "₸" not in resp.answer


def test_orchestrator_survives_planner_failure() -> None:
    gem = FakeGemini(fail_planner=True, writer_texts=["Расскажу о клинике и направлениях."])
    resp = _run(handle_medical_center_chat(gem, _request("расскажите о клинике")))
    assert resp.metadata["planner_llm_used"] is False
    assert resp.answer


def test_planner_timeout_returns_safe_response() -> None:
    from unittest.mock import patch

    gem = FakeGemini(writer_texts=["Приём терапевта — 12 000 ₸."])

    async def _timeout(*args, **kwargs):
        raise asyncio.TimeoutError("simulated planner timeout")

    with patch("app.medical_center_demo.plan_conversation_turn", side_effect=_timeout):
        resp = _run(handle_medical_center_chat(gem, _request("сколько стоит терапевт?")))

    assert resp.answer
    assert resp.metadata.get("planner_timeout") is True


def test_writer_timeout_returns_safe_fallback() -> None:
    from unittest.mock import patch

    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"))

    async def _timeout(*args, **kwargs):
        raise asyncio.TimeoutError("simulated writer timeout")

    with patch("app.medical_center_demo.write_response", side_effect=_timeout):
        resp = _run(handle_medical_center_chat(gem, _request("сколько стоит терапевт?")))

    assert resp.answer
    assert "₸" not in resp.answer
    assert resp.metadata.get("writer_timeout") is True


def test_repair_timeout_returns_safe_fallback() -> None:
    from unittest.mock import patch

    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"))

    async def _timeout_on_repair(*args, repair=None, **kwargs):
        if repair:
            raise asyncio.TimeoutError("simulated repair timeout")
        return "МРТ стоит 25 000 ₸."  # invented price → triggers repair

    with patch("app.medical_center_demo.write_response", side_effect=_timeout_on_repair):
        resp = _run(handle_medical_center_chat(gem, _request("сколько стоит МРТ?")))

    assert resp.answer
    assert "25 000" not in resp.answer
    assert resp.metadata.get("repair_timeout") is True


def test_stage_timeouts_fit_frontend_budget() -> None:
    from app.medical_center_demo import _PLANNER_TIMEOUT, _REPAIR_TIMEOUT, _WRITER_TIMEOUT

    assert _PLANNER_TIMEOUT + _WRITER_TIMEOUT + _REPAIR_TIMEOUT <= 30


# ---------------------------------------------------------------------------
# Reclassifiers
# ---------------------------------------------------------------------------

def test_medical_advice_reclassifier_retags_medication_question() -> None:
    plan = _default_planner(current_intent="ask_price", recommended_next_step="ask_contact")
    out = reclassify_medical_advice_question("Что мне принять от головной боли?", plan)
    assert out["current_intent"] == "medical_advice_request"
    assert out["recommended_next_step"] == "none"


def test_medical_advice_reclassifier_retags_lab_question() -> None:
    out = reclassify_medical_advice_question(
        "Расшифруйте мои анализы, пожалуйста", _default_planner(current_intent="answer_question")
    )
    assert out["current_intent"] == "medical_advice_request"


def test_medical_advice_reclassifier_leaves_price_question() -> None:
    out = reclassify_medical_advice_question(
        "Сколько стоит приём кардиолога?", _default_planner(current_intent="ask_price")
    )
    assert out["current_intent"] == "ask_price"


def test_medical_advice_reclassifier_leaves_protected_intents() -> None:
    for intent in ("wants_booking", "contact", "offensive", "correction"):
        out = reclassify_medical_advice_question(
            "что мне принять?", _default_planner(current_intent=intent)
        )
        assert out["current_intent"] == intent


def test_discount_reclassifier_retags_price_intent() -> None:
    out = reclassify_discount_question(
        "А есть скидки для пенсионеров?", _default_planner(current_intent="ask_price")
    )
    assert out["current_intent"] == "ask_discount"


def test_discount_honest_answer_passes_without_repair() -> None:
    honest = (
        "Пенсионерам действует скидка 10% на консультации специалистов по будням до 13:00. "
        "Остальные условия уточнит администратор."
    )
    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"), writer_texts=[honest])
    resp = _run(handle_medical_center_chat(gem, _request("А есть скидки для пенсионеров?")))
    assert resp.answer == honest
    assert gem.writer_calls == 1
    assert resp.metadata["current_intent"] == "ask_discount"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def test_looks_like_contact_international() -> None:
    for good in (
        "77777102402", "+77777102402", "87777102402", "+7 777 710 24 02",
        "8 777 710 24 02", "+1 415 555 2671", "+44 7700 900123",
        "+90 555 123 45 67", "+49 151 23456789", "7012345678", "0555 123 45 67",
        "@damir", "t.me/damir", "мой телеграм @damir_k",
    ):
        assert looks_like_contact(good), good
    for bad in ("хочу узнать цены", "123", "hello", "телефон позже"):
        assert not looks_like_contact(bad), bad


def test_classify_contact() -> None:
    assert classify_contact("мой телеграм @damir_k") == "telegram"
    assert classify_contact("t.me/damir") == "telegram"
    assert classify_contact("+1 415 555 2671") == "phone"      # US 11 digits
    assert classify_contact("+44 7700 900123") == "phone"      # UK 12 digits
    assert classify_contact("713812732873") == "phone"         # 12 digits — valid intl now
    assert classify_contact("Дамир 23 77777102402") == "phone"  # phone + age noise
    assert classify_contact("123") == "none"                   # too short to be a phone
    assert classify_contact("1234567890123456789") == "phone_invalid"  # 19 digits
    assert classify_contact("хочу узнать цены") == "none"


def test_extract_contact_cleans_phone_from_noise() -> None:
    assert extract_contact("Дамир 23 77777102402") == "77777102402"
    assert extract_contact("мой номер +7 777 710 24 02") == "+7 777 710 24 02"
    assert extract_contact("телеграм @damir_k").lower().endswith("@damir_k")
    assert extract_contact("зовут Дамир") == ""


def test_looks_like_invalid_phone_only_when_too_long() -> None:
    # Valid international numbers are NOT invalid.
    assert not looks_like_invalid_phone("713812732873")   # 12 digits — valid now
    assert not looks_like_invalid_phone("+7 701 222 33 44")
    # A digit-dominated run longer than 15 digits is a failed attempt.
    assert looks_like_invalid_phone("12345678901234567890")
    # Prose that merely contains a long number must not be hijacked.
    assert not looks_like_invalid_phone(
        "Меня выставили счёт на 123456789 тенге, это дороговато для меня"
    )


def test_invalid_phone_short_circuits_without_llm() -> None:
    gem = FakeGemini(planner=_default_planner(current_intent="contact"))
    history = [
        _msg("user", "хочу записаться"),
        _msg("assistant", "Оставьте, пожалуйста, ваше имя и WhatsApp/телефон для связи."),
    ]
    # A 20-digit run is implausible for any country -> deterministic re-ask.
    resp = _run(handle_medical_center_chat(gem, _request("12345678901234567890", history=history)))
    assert resp.answer == INVALID_CONTACT_ANSWER
    assert gem.planner_calls == 0
    assert gem.writer_calls == 0
    assert resp.metadata["invalid_contact_short_circuit"] is True
    assert resp.lead_status != "contact_collected"
    assert not resp.metadata["state"]["contact"]


def test_price_intent_appends_booking_cta_hint() -> None:
    state = ConversationState(specialty="невролог", greeting_already_sent=True)
    planner = _default_planner(
        current_intent="ask_price",
        should_pause_qualification=True,
        recommended_next_step="none",
    )
    plan = build_turn_plan(state, planner)
    assert "приглашение к записи" in plan.casefold()
    # The pause line must not suppress the CTA for a price question.
    assert "на паузе" not in plan.casefold()


def test_price_cta_suppressed_once_offered_or_contact_known() -> None:
    planner = _default_planner(current_intent="ask_price", recommended_next_step="none")
    # Already offered booking → no repeat CTA.
    offered = ConversationState(booking_cta_mentioned=True, greeting_already_sent=True)
    assert "приглашение к записи" not in build_turn_plan(offered, planner).casefold()
    # Contact already on file → no CTA (do not re-push booking).
    have_contact = ConversationState(contact="+7 701 222 33 44", greeting_already_sent=True)
    assert "приглашение к записи" not in build_turn_plan(have_contact, planner).casefold()


def test_detect_symptom_specialty_routes_common_complaints() -> None:
    assert detect_symptom_specialty("болит живот") == "гастроэнтеролог или терапевт"
    assert detect_symptom_specialty("У меня болит спина") == "невролог"
    assert detect_symptom_specialty("болит голова уже неделю") == "невролог"
    assert detect_symptom_specialty("сыпь на коже и зуд") == "дерматолог"
    assert detect_symptom_specialty("болит горло и ухо") == "ЛОР"
    assert detect_symptom_specialty("болит зуб уже два дня") == "стоматолог"
    assert detect_symptom_specialty("кровоточат дёсны") == "стоматолог"
    # A price question that names a specialty must NOT be read as a symptom.
    assert detect_symptom_specialty("сколько стоит приём невролога") is None
    assert detect_symptom_specialty("хочу узнать цены") is None


def test_dentist_normalization_and_slots() -> None:
    state = ConversationState()
    apply_planner_updates(state, _default_planner(slots={"specialty": "dentist"}))
    assert state.specialty == "стоматолог"

    gem = FakeGemini(planner=_default_planner(
        current_intent="wants_booking", slots={"specialty": "стоматолог"},
    ))
    resp = _run(handle_medical_center_chat(gem, _request("Можете записать к стоматологу?")))
    low = resp.answer.casefold()
    assert "к стоматологу" in low  # correct dative form
    assert "17:00" in low and "14:00" in low  # controlled demo slots present
    assert resp.metadata["conversation_status"] == "slots_offered"


def test_symptom_routing_fallback_when_llm_down() -> None:
    # Planner LLM down -> fallback plan; writer LLM down -> outer safe fallback.
    # A symptom must still route to a specialist and ask a clarifying question,
    # never dump to "leave your contact".
    gem = FakeGemini(fail_planner=True)
    resp = _run(handle_medical_center_chat(gem, _request("болит живот")))
    low = resp.answer.casefold()
    assert "гастроэнтеролог" in low or "терапевт" in low
    assert "?" in resp.answer  # asks a clarifying question
    assert "оставьте" not in low  # not the generic admin-contact dump
    assert resp.lead_status != "contact_collected"


def test_symptom_routing_fallback_skipped_once_contact_known() -> None:
    # With a contact already on file, a degraded turn must not re-route/re-ask;
    # it confirms via the contact-aware fallback instead.
    state = ConversationState(contact="+7 701 222 33 44")
    answer = build_safe_fallback(_default_planner(current_intent="answer_question"), state, "болит живот")
    assert "гастроэнтеролог" not in answer.casefold()


# ---------------------------------------------------------------------------
# Appointment flow (deterministic demo slots)
# ---------------------------------------------------------------------------

def _booking_history() -> list:
    return [
        _msg("user", "болит голова уже три дня, температура"),
        _msg("assistant", "При головной боли и температуре обычно начинают с терапевта."),
        _msg("user", "сколько стоит?"),
        _msg("assistant", "Первичная консультация терапевта стоит 12 000 ₸."),
    ]


def test_symptom_turn_plan_invites_slots() -> None:
    state = ConversationState(specialty="терапевт", greeting_already_sent=True)
    plan = build_turn_plan(state, _default_planner(current_intent="symptom_description")).casefold()
    assert "приглашение к записи" in plan
    # The plan must steer the writer to rephrase, not repeat verbatim.
    assert "перефраз" in plan


def test_specialty_normalized_to_russian() -> None:
    state = ConversationState()
    apply_planner_updates(state, _default_planner(slots={"specialty": "therapist"}))
    assert state.specialty == "терапевт"


def test_booking_offers_slots_and_keeps_specialty() -> None:
    gem = FakeGemini(planner=_default_planner(
        current_intent="wants_booking", slots={"specialty": "терапевт"},
    ))
    resp = _run(handle_medical_center_chat(
        gem, _request("Можете записать?", history=_booking_history())
    ))
    low = resp.answer.casefold()
    assert "демо-окна" in low
    assert "завтра 10:00" in low and "15:30" in low
    assert resp.metadata["conversation_status"] == "slots_offered"
    # Does NOT re-ask the specialist, does NOT defer to the administrator.
    assert "какому специалист" not in low
    assert "администратор" not in low
    assert gem.writer_calls == 0  # deterministic, no LLM writer


def test_date_question_returns_concrete_slots() -> None:
    gem = FakeGemini(planner=_default_planner(
        current_intent="wants_booking", slots={"specialty": "терапевт"},
    ))
    resp = _run(handle_medical_center_chat(
        gem, _request("На какую дату можно?", history=_booking_history())
    ))
    low = resp.answer.casefold()
    assert "10:00" in low and "11:00" in low
    assert "администратор" not in low


def test_no_booking_confirm_before_contact() -> None:
    history = _booking_history() + [
        _msg("user", "Можете записать?"),
        _msg("assistant", "К терапевту есть демо-окна: завтра 10:00, завтра 15:30 или послезавтра 11:00.\n\nКакое время вам удобнее?"),
    ]
    gem = FakeGemini(planner=_default_planner(
        current_intent="wants_booking", slots={"specialty": "терапевт"},
    ))
    resp = _run(handle_medical_center_chat(gem, _request("Завтра 15:30", history=history)))
    low = resp.answer.casefold()
    assert "записали вас" not in low          # must NOT confirm yet
    assert "оставьте" in low and "имя" in low  # asks for missing fields
    assert resp.metadata["conversation_status"] == "awaiting_contact"


def test_booking_confirmed_when_all_fields_present() -> None:
    history = _booking_history() + [
        _msg("user", "Завтра 15:30"),
        _msg("assistant", "Отлично, завтра 15:30 к терапевту.\n\nДля записи оставьте, пожалуйста, имя, возраст, WhatsApp или телефон."),
    ]
    gem = FakeGemini(planner=_default_planner(
        current_intent="contact",
        slots={"specialty": "терапевт", "patient_name": "Дамир", "age": "22", "contact": "+7 701 000 00 00"},
    ))
    resp = _run(handle_medical_center_chat(
        gem, _request("Дамир, 22 года, +7 701 000 00 00", history=history)
    ))
    low = resp.answer.casefold()
    assert "готово, дамир!" in low  # confirmation greets the patient by name
    assert "записали вас на завтра 15:30 к терапевту" in low
    assert resp.metadata["conversation_status"] == "booking_created"
    assert resp.lead_status == "contact_collected"
    assert resp.metadata["medical_lead_status"] == "appointment_created"


def test_emergency_preempts_booking_flow() -> None:
    history = _booking_history() + [
        _msg("user", "Можете записать?"),
        _msg("assistant", "К терапевту есть демо-окна: завтра 10:00, завтра 15:30 или послезавтра 11:00.\n\nКакое время вам удобнее?"),
    ]
    gem = FakeGemini(planner=_default_planner(current_intent="wants_booking", slots={"specialty": "терапевт"}))
    resp = _run(handle_medical_center_chat(
        gem, _request("Сильная боль в груди и трудно дышать", history=history)
    ))
    assert resp.answer == EMERGENCY_ANSWER
    assert "демо-окна" not in resp.answer.casefold()
    assert gem.planner_calls == 0  # short-circuit before any LLM


# ---------------------------------------------------------------------------
# Natural-language slot selection + loop prevention
# ---------------------------------------------------------------------------

def test_resolve_slot_natural_language() -> None:
    # ЛОР demo slots: завтра 11:00, завтра 16:00, послезавтра 12:00.
    assert resolve_slot("ЛОР", "В 16") == ("matched", "завтра 16:00")
    assert resolve_slot("ЛОР", "В 4 дня") == ("matched", "завтра 16:00")
    assert resolve_slot("ЛОР", "Завтра в 4") == ("matched", "завтра 16:00")
    assert resolve_slot("ЛОР", "Завтра в 16:00") == ("matched", "завтра 16:00")
    assert resolve_slot("ЛОР", "второй вариант") == ("matched", "завтра 16:00")
    # Bare small hour with no day/qualifier -> suggest, don't guess silently.
    assert resolve_slot("ЛОР", "В 4") == ("suggest", "завтра 16:00")
    # A phone number must not be read as a slot.
    assert resolve_slot("ЛОР", "Дамир 23 77777102402") == ("none", None)


def _lor_offer_history() -> list:
    return [
        _msg("user", "покраснение и чихаю"),
        _msg("assistant", "По описанным симптомам вам может помочь ЛОР-врач."),
        _msg("assistant", "К ЛОРу есть демо-окна: завтра 11:00, завтра 16:00 или послезавтра 12:00.\n\nКакое время вам удобнее?"),
    ]


def _lor_planner(**kw):
    slots = {"specialty": "ЛОР"}
    slots.update(kw.pop("slots", {}))
    return _default_planner(current_intent=kw.pop("current_intent", "wants_booking"), slots=slots, **kw)


def test_natural_slot_selection_advances_to_contact() -> None:
    # "В 16" is understood -> move straight to collecting contact, not re-listing.
    gem = FakeGemini(planner=_lor_planner())
    resp = _run(handle_medical_center_chat(gem, _request("В 16", history=_lor_offer_history())))
    low = resp.answer.casefold()
    assert "демо-окна" not in low          # no repeated slot list
    assert "завтра 16:00" in low
    assert "оставьте" in low                # asks for name/contact
    assert resp.metadata["conversation_status"] == "awaiting_contact"
    assert resp.metadata["state"]["selected_slot"] == "завтра 16:00"


def test_ambiguous_slot_asks_confirmation_not_relist() -> None:
    gem = FakeGemini(planner=_lor_planner())
    resp = _run(handle_medical_center_chat(gem, _request("В 4", history=_lor_offer_history())))
    low = resp.answer.casefold()
    assert "правильно понял, хотите завтра 16:00" in low
    assert "демо-окна" not in low  # a confirmation, not the full list again


def test_affirmation_confirms_suggested_slot() -> None:
    history = _lor_offer_history() + [
        _msg("user", "В 4"),
        _msg("assistant", "Правильно понял, хотите завтра 16:00?"),
    ]
    gem = FakeGemini(planner=_lor_planner(current_intent="contact"))
    resp = _run(handle_medical_center_chat(gem, _request("да", history=history)))
    assert resp.metadata["state"]["selected_slot"] == "завтра 16:00"
    assert resp.metadata["conversation_status"] == "awaiting_contact"


def test_unmapped_reply_after_offer_clarifies_once() -> None:
    # Still trying to book (wants_booking) but the time can't be parsed -> the
    # handler engages and clarifies ONCE instead of repeating the slot list.
    gem = FakeGemini(planner=_lor_planner(current_intent="wants_booking"))
    resp = _run(handle_medical_center_chat(gem, _request("давайте не уверен", history=_lor_offer_history())))
    low = resp.answer.casefold()
    assert "демо-окна" not in low  # must NOT repeat the same list
    assert "не совсем понял" in low and "например" in low
    assert gem.writer_calls == 0  # deterministic clarification, no LLM loop


def test_transcript_phone_accepted_and_confirms() -> None:
    # The exact failing transcript reply: phone with an age prefix, no '+'.
    history = _lor_offer_history() + [
        _msg("user", "В 16"),
        _msg("assistant", "Отлично, завтра 16:00 к ЛОРу.\n\nДля записи оставьте, пожалуйста, имя, возраст, WhatsApp или телефон."),
    ]
    gem = FakeGemini(planner=_lor_planner(
        current_intent="contact",
        slots={"patient_name": "Дамир", "age": "23", "contact": "77777102402"},
    ))
    resp = _run(handle_medical_center_chat(gem, _request("Дамир 23 77777102402", history=history)))
    low = resp.answer.casefold()
    assert "не вижу контакт" not in low         # phone must be accepted
    assert "готово, дамир!" in low
    assert "завтра 16:00 к лору" in low
    assert resp.metadata["conversation_status"] == "booking_created"
    assert resp.lead_status == "contact_collected"


def test_invalid_contact_in_booking_reasks_internationally() -> None:
    history = _lor_offer_history() + [
        _msg("user", "В 16"),
        _msg("assistant", "Отлично, завтра 16:00 к ЛОРу.\n\nДля записи оставьте, пожалуйста, имя, возраст, WhatsApp или телефон."),
    ]
    gem = FakeGemini(planner=_lor_planner(current_intent="contact"))
    resp = _run(handle_medical_center_chat(gem, _request("123", history=history)))
    low = resp.answer.casefold()
    assert "не вижу контакт" in low
    assert "международном формате" in low
    assert "11 цифр" not in low  # never country-specific
    assert resp.metadata["conversation_status"] != "booking_created"


def test_reschedule_after_contact_ask_acknowledges_change() -> None:
    # Slot chosen (завтра 16:00), we asked for contact, user changes to
    # "послезавтра днём" -> acknowledge the NEW slot, never "Не вижу контакт".
    history = _lor_offer_history() + [
        _msg("user", "в 4 завтра"),
        _msg("assistant", "Отлично, завтра 16:00 к ЛОРу.\n\nДля записи оставьте, пожалуйста, имя, возраст, телефон или WhatsApp."),
    ]
    gem = FakeGemini(planner=_lor_planner(current_intent="wants_booking"))
    resp = _run(handle_medical_center_chat(
        gem, _request("а нет, давайте послезавтра днём", history=history)
    ))
    low = resp.answer.casefold()
    assert "не вижу контакт" not in low
    assert "выбрали послезавтра 12:00 к лору" in low  # acknowledges the change
    assert "демо-окна" not in low                     # does not re-list slots
    assert "оставьте" in low                          # asks for the missing contact
    assert resp.metadata["state"]["selected_slot"] == "послезавтра 12:00"
    assert resp.metadata["conversation_status"] == "awaiting_contact"
    assert gem.writer_calls == 0                       # deterministic, no dead-end LLM


def test_affirmation_after_price_cta_offers_slots_not_dead_end() -> None:
    # "хорошо" after the assistant invited booking must offer slots, not "Принято.".
    history = [
        _msg("user", "болит ухо"),
        _msg("assistant", "Если болит ухо, лучше начать с ЛОР-врача. Принимает Тимур Серикович Ахметов."),
        _msg("user", "сколько стоит?"),
        _msg("assistant", "Первичный приём у ЛОР-врача стоит 10 500 ₸.\n\nМогу показать ближайшие окна к ЛОРу."),
    ]
    gem = FakeGemini(planner=_lor_planner(current_intent="smalltalk"))
    resp = _run(handle_medical_center_chat(gem, _request("хорошо", history=history)))
    low = resp.answer.casefold()
    assert "демо-окна" in low and "11:00" in low  # offers concrete slots
    assert "принято" not in low
    assert resp.metadata["conversation_status"] == "slots_offered"
    assert gem.writer_calls == 0


def test_symptom_normalization_sneezing_redness() -> None:
    out = normalize_symptom_terms("redness and sneezing")
    assert "покраснение" in out and "чихание" in out
    assert "redness" not in out.lower() and "sneezing" not in out.lower()


def test_build_state_sticky_emergency_from_history() -> None:
    history = [
        _msg("user", "Сильная боль в груди и трудно дышать"),
        _msg("assistant", EMERGENCY_ANSWER),
    ]
    state = build_conversation_state(history, "Спасибо, уже лучше")
    assert state.urgency_flag == "emergency"


def test_planner_can_upgrade_to_urgent_but_not_downgrade_emergency() -> None:
    state = ConversationState()
    apply_planner_updates(state, _default_planner(slots={"urgency": "urgent"}))
    assert state.urgency_flag == "urgent"

    emergency = ConversationState(urgency_flag="emergency")
    apply_planner_updates(emergency, _default_planner(slots={"urgency": "urgent"}))
    assert emergency.urgency_flag == "emergency"


def test_apply_planner_updates_protects_stable_slots() -> None:
    state = ConversationState(specialty="кардиолог")
    apply_planner_updates(state, _default_planner(correction=False, slots={"specialty": "невролог"}))
    assert state.specialty == "кардиолог"
    apply_planner_updates(state, _default_planner(correction=True, slots={"specialty": "невролог"}))
    assert state.specialty == "невролог"


def test_build_state_collects_contact_and_asked_questions() -> None:
    history = [
        _msg("user", "хочу к врачу"),
        _msg("assistant", "Подскажите, какое время удобно?"),
        _msg("user", "мой номер +7 701 222 33 44"),
    ]
    state = build_conversation_state(history, "суббота утром")
    assert state.contact
    assert "preferred_time" in state.recent_questions_asked


# ---------------------------------------------------------------------------
# Safe fallbacks
# ---------------------------------------------------------------------------

def test_safe_fallbacks_are_clean_and_pass_guardrails() -> None:
    for intent in (
        "ask_price", "ask_discount", "medical_advice_request", "wants_booking",
        "symptom_description", "offensive", "objection", "smalltalk",
    ):
        planner = _default_planner(current_intent=intent)
        fb = build_safe_fallback(planner)
        low = fb.casefold()
        assert "₸" not in fb, intent
        assert "ибупрофен" not in low and "антибиотик" not in low, intent
        assert "записал вас" not in low, intent
        res = validate_answer(fb, ConversationState(), planner)
        assert not res.failed, f"{intent}: {res.fix}"


def test_medical_advice_fallback_is_a_refusal() -> None:
    fb = build_safe_fallback(_default_planner(current_intent="medical_advice_request"))
    low = fb.casefold()
    assert "не врач" in low or "врач на приёме" in low
    assert "назнач" in low  # explains that a doctor prescribes


def test_contact_aware_fallback_does_not_reask_contact() -> None:
    state = ConversationState(contact="+7 701 222 33 44", age="5")
    for intent in ("contact", "wants_booking", "ask_price", "smalltalk"):
        fb = build_safe_fallback(_default_planner(current_intent=intent), state)
        assert "оставьте" not in fb.casefold(), intent
