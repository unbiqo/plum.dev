"""Unit tests for the LLM-first English School demo agent.

These run without any API key — the Gemini service is stubbed (``FakeGemini``).
They assert the orchestration logic: state reconstruction + merge, deterministic
guardrails, repair flow, intent-aware safe fallback, no-crash behavior, and
metadata. Real LLM behavior is covered separately by the opt-in live eval suite
(``test_english_school_live.py``).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.english_school_demo import (
    ENGLISH_SCHOOL_INSTANCE_ID,
    handle_english_school_chat,
)
from app.english_school_guardrails import (
    build_safe_fallback,
    kb_price_set,
    validate_answer,
)
from app.english_school_kb import (
    format_kb_context,
    get_full_kb_context,
)
from app.english_school_planner import plan_conversation_turn, reclassify_general_question
from app.english_school_state import (
    ConversationState,
    apply_planner_updates,
    build_conversation_state,
    looks_like_contact,
)
from app.english_school_writer import build_turn_plan, write_response
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
        "question_to_answer": "что есть",
        "response_goal": "ответить",
        "must_mention": [],
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
        chat_id="t1",
        instance_id=ENGLISH_SCHOOL_INSTANCE_ID,
        message=message,
        chat_history=history or [],
    )


def _run(coro):
    """Drive a coroutine to completion without pytest-asyncio."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# KB fact tests (migrated — must keep holding after the redesign)
# ---------------------------------------------------------------------------

def test_instance_id_unchanged() -> None:
    assert ENGLISH_SCHOOL_INSTANCE_ID == "damiworks_english_school_demo"


def test_kb_contains_correct_individual_price() -> None:
    kb = get_full_kb_context()
    assert "9 500" in kb and "72 000" in kb


def test_kb_contains_all_program_prices() -> None:
    kb = get_full_kb_context()
    for price in ("39 000", "42 000", "45 000", "58 000", "9 500", "72 000", "15 000"):
        assert price in kb


def test_kb_has_no_damiworks_branding() -> None:
    assert "damiworks" not in get_full_kb_context().casefold()


def test_kb_price_set_is_exact() -> None:
    assert kb_price_set() == frozenset({7000, 9500, 15000, 39000, 42000, 45000, 58000, 72000})


def test_format_kb_context_wraps_chunks() -> None:
    out = format_kb_context([{"text": "пример", "heading": "h", "chunk_index": 0}])
    assert "пример" in out and "БАЗА ЗНАНИЙ" in out


# ---------------------------------------------------------------------------
# State: contact detection + reconstruction + merge
# ---------------------------------------------------------------------------

def test_looks_like_contact_phone_and_telegram() -> None:
    assert looks_like_contact("+7 700 415 77 21")
    assert looks_like_contact("мой телеграм @damir_k")
    assert not looks_like_contact("просто хочу узнать про цены")


def test_build_state_records_asked_questions_and_contact() -> None:
    history = [
        _msg("user", "хочу английский"),
        _msg("assistant", "В каком городе удобнее заниматься?"),
        _msg("user", "Астана, мой номер +7 701 222 33 44"),
    ]
    state = build_conversation_state(history, "+7 701 222 33 44")
    assert "city" in state.recent_questions_asked
    assert state.contact


def test_apply_planner_updates_fills_unknown_slots() -> None:
    state = ConversationState()
    apply_planner_updates(state, _default_planner(slots={"program": "ielts", "city": "Астана"}))
    assert state.program == "ielts"
    assert state.city == "Астана"


def test_apply_planner_updates_protects_stable_slot_without_correction() -> None:
    state = ConversationState(city="Астана")
    apply_planner_updates(state, _default_planner(correction=False, slots={"city": "Алматы"}))
    assert state.city == "Астана"


def test_apply_planner_updates_overwrites_on_correction() -> None:
    state = ConversationState(program="kids")
    apply_planner_updates(state, _default_planner(correction=True, slots={"program": "ielts"}))
    assert state.program == "ielts"


def test_apply_planner_updates_accepts_free_text_location() -> None:
    state = ConversationState(preferred_location_text="EXPO")
    apply_planner_updates(state, _default_planner(slots={"preferred_location_text": "Турана"}))
    assert state.preferred_location_text == "Турана"


def test_apply_planner_updates_ignores_empty_values() -> None:
    state = ConversationState(city="Астана")
    apply_planner_updates(state, _default_planner(slots={"city": ""}))
    assert state.city == "Астана"


# ---------------------------------------------------------------------------
# Guardrail: invented prices (monetary-only, normalized)
# ---------------------------------------------------------------------------

def test_guardrail_rejects_invented_price() -> None:
    state = ConversationState()
    res = validate_answer("Индивидуально — 100 000 ₸ за занятие.", state, _default_planner())
    assert res.failed and not res.checks["no_invented_prices"]


def test_guardrail_accepts_real_prices_and_non_price_numbers() -> None:
    state = ConversationState()
    answer = (
        "Индивидуально — 9 500 ₸ за 60 минут, пакет из 8 занятий — 72 000 ₸. "
        "Группа IELTS — 58 000 ₸/мес за 12 занятий, 3 раза в неделю по 90 минут."
    )
    res = validate_answer(answer, state, _default_planner(current_intent="ask_price"))
    assert not res.failed, res.fix


def test_guardrail_price_normalization_variants() -> None:
    state = ConversationState()
    # 58000 written without a space must still match the KB's "58 000".
    res = validate_answer("Группа стоит 58000 ₸ в месяц.", state, _default_planner())
    assert res.checks["no_invented_prices"]


# ---------------------------------------------------------------------------
# Guardrail: guarantees, repeated slot, price-present, filler
# ---------------------------------------------------------------------------

def test_guardrail_rejects_score_guarantee() -> None:
    res = validate_answer("Мы гарантируем балл 7.0 на IELTS.", ConversationState(), _default_planner())
    assert res.failed and not res.checks["no_guarantees"]


def test_guardrail_rejects_reasking_known_slot() -> None:
    state = ConversationState(city="Астана")
    res = validate_answer("Хорошо. А в каком городе удобнее заниматься?", state, _default_planner())
    assert res.failed and not res.checks["no_repeated_known_slot"]


def test_guardrail_requires_price_when_price_asked() -> None:
    res = validate_answer(
        "Да, конечно, расскажу подробнее.",
        ConversationState(),
        _default_planner(current_intent="ask_price"),
    )
    assert res.failed and res.checks["price_present_when_asked"] is False


def test_guardrail_rejects_filler() -> None:
    res = validate_answer(
        "Понимаю ваше беспокойство, мы делаем всё возможное.",
        ConversationState(),
        _default_planner(),
    )
    assert res.failed and not res.checks["no_filler"]


@pytest.mark.parametrize(
    "answer",
    [
        "Отлично. А в каком районе ближайшего филиала будете заниматься?",
        "Подскажите, какая локация удобнее?",
        "Какой филиал удобнее — на правом берегу или в EXPO?",
        "Где вам удобнее заниматься?",
        "Уточните, пожалуйста, ближайшего филиала какой район?",
    ],
)
def test_guardrail_rejects_location_question_when_location_known(answer: str) -> None:
    state = ConversationState(preferred_location_text="Турана")
    res = validate_answer(answer, state, _default_planner())
    assert res.failed and not res.checks["no_repeated_known_slot"]


def test_guardrail_allows_factual_answer_when_location_known() -> None:
    # A real answer that does not ask for location must still pass.
    state = ConversationState(preferred_location_text="Турана")
    res = validate_answer(
        "Хорошо, ориентируемся на район Турана. Индивидуально — 9 500 ₸ за 60 минут.",
        state,
        _default_planner(),
    )
    assert not res.failed, res.fix


def test_guardrail_clean_answer_passes() -> None:
    res = validate_answer(
        "Да, индивидуальные занятия есть — 9 500 ₸ за 60 минут.",
        ConversationState(),
        _default_planner(),
    )
    assert not res.failed


# ---------------------------------------------------------------------------
# Intent-aware safe fallback
# ---------------------------------------------------------------------------

def test_safe_fallback_is_intent_aware() -> None:
    price = build_safe_fallback(_default_planner(current_intent="ask_price"))
    guarantee = build_safe_fallback(_default_planner(current_intent="objection"))
    contact = build_safe_fallback(_default_planner(current_intent="wants_trial"))
    general = build_safe_fallback(_default_planner(current_intent="smalltalk"))
    assert price != guarantee != contact
    # No fallback may invent a price or a guarantee.
    for text in (price, guarantee, contact, general):
        assert "₸" not in text
        assert "гаранти" not in text.casefold()


# ---------------------------------------------------------------------------
# Planner (mocked)
# ---------------------------------------------------------------------------

def test_planner_parses_json() -> None:
    gem = FakeGemini(planner=_default_planner(current_intent="ask_price", slots={"city": "Астана"}))
    plan = _run(plan_conversation_turn("сколько стоит?", [], ConversationState(), "KB", gem))
    assert plan["current_intent"] == "ask_price"
    assert plan["slots"]["city"] == "Астана"
    assert "_error" not in plan


def test_planner_falls_back_on_failure() -> None:
    gem = FakeGemini(fail_planner=True)
    plan = _run(plan_conversation_turn("сколько стоит?", [], ConversationState(), "KB", gem))
    assert plan["current_intent"] == "answer_question"
    assert plan["should_pause_qualification"] is True
    assert "_error" in plan


# ---------------------------------------------------------------------------
# Writer turn plan
# ---------------------------------------------------------------------------

def test_turn_plan_forbids_known_slots() -> None:
    state = ConversationState(city="Астана", preferred_location_text="Турана")
    plan = build_turn_plan(state, _default_planner(do_not_ask=["online_offline"]))
    assert "НЕ спрашивай" in plan
    assert "город" in plan and "район" in plan


def test_turn_plan_signals_paused_qualification() -> None:
    plan = build_turn_plan(
        ConversationState(),
        _default_planner(should_pause_qualification=True, recommended_next_step="none"),
    )
    assert "пауз" in plan.casefold()


def test_writer_returns_stripped_text() -> None:
    gem = FakeGemini(writer_texts=["  Да, есть.  "])
    out = _run(write_response("есть индивидуальные?", [], ConversationState(), _default_planner(), "KB", gem))
    assert out == "Да, есть."


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def test_orchestrator_happy_path_metadata() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price", slots={"city": "Астана"}),
        writer_texts=["Индивидуально — 9 500 ₸ за 60 минут, пакет 8 занятий — 72 000 ₸."],
    )
    resp = _run(handle_english_school_chat(gem, _request("сколько стоят индивидуальные?")))
    md = resp.metadata
    assert md["planner_llm_used"] is True
    assert md["writer_llm_used"] is True
    assert md["current_intent"] == "ask_price"
    assert md["should_pause_qualification"] is True
    assert md["repaired_answer"] is False
    assert md["validation_result"]["failed"] is False
    assert md["state"]["city"] == "Астана"
    assert "9 500" in resp.answer


def test_orchestrator_repairs_once_on_guardrail_failure() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price"),
        writer_texts=[
            "Индивидуально стоит 100 000 ₸.",  # invented price -> fails
            "Индивидуально — 9 500 ₸ за 60 минут.",  # repaired -> passes
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("сколько стоят индивидуальные?")))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True
    assert "9 500" in resp.answer


def test_orchestrator_uses_safe_fallback_when_repair_still_fails() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price"),
        writer_texts=[
            "Индивидуально стоит 100 000 ₸.",  # fail
            "Нет, всё равно 100 000 ₸.",  # repair still fails
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("сколько стоят индивидуальные?")))
    assert resp.metadata["repaired_answer"] is True
    assert "100 000" not in resp.answer  # fell back to a safe answer
    assert resp.answer == build_safe_fallback(_default_planner(current_intent="ask_price"))


def test_orchestrator_never_crashes_on_writer_failure() -> None:
    # Planner OK, but the writer LLM is down: the turn must NOT raise (the old
    # bug surfaced as the frontend "Что-то пошло не так").
    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"), writer_texts=[])
    resp = _run(handle_english_school_chat(gem, _request("сколько стоят индивидуальные?")))
    assert resp.answer  # a safe fallback, not an exception
    assert resp.metadata.get("error")
    assert "₸" not in resp.answer


def test_orchestrator_survives_planner_failure_and_still_answers() -> None:
    gem = FakeGemini(fail_planner=True, writer_texts=["Расскажу про программы школы."])
    resp = _run(handle_english_school_chat(gem, _request("расскажите о школе")))
    assert resp.metadata["planner_llm_used"] is False
    assert resp.metadata["writer_llm_used"] is True
    assert resp.answer


# ---------------------------------------------------------------------------
# Compact mode + no-repeat (PART 1–3, 6–8 guardrail tests)
# ---------------------------------------------------------------------------

def test_broad_price_question_does_not_produce_full_bullet_list() -> None:
    # 5 bullet items in response to a broad price question → no_verbose_list fails.
    bullet_answer = (
        "• Kids English: 39 000 ₸/мес\n"
        "• Teen English: 42 000 ₸/мес\n"
        "• IELTS Foundation: 58 000 ₸/мес\n"
        "• Индивидуально: 9 500 ₸ за урок\n"
        "• Speaking Club: 15 000 ₸/мес"
    )
    res = validate_answer(
        bullet_answer,
        ConversationState(),
        _default_planner(current_intent="ask_relevant_price"),
    )
    assert res.failed and not res.checks["no_verbose_list"]


def test_broad_price_overview_plan_contains_goal_and_next_step() -> None:
    # build_turn_plan for ask_relevant_price with a clarifying next step.
    plan = build_turn_plan(
        ConversationState(),
        _default_planner(
            current_intent="ask_relevant_price",
            response_goal="дать краткий диапазон цен и уточнить возраст/программу",
            recommended_next_step="ask_age",
        ),
    )
    assert "краткий" in plan
    assert "возраст" in plan  # from ask_age hint


def test_objection_not_repeat_individual_price() -> None:
    # must_not_repeat=["individual_price"] + answer repeating 9 500 ₸ → no_repeated_price fails.
    res = validate_answer(
        "Понимаем. Индивидуальные занятия стоят 9 500 ₸ за урок.",
        ConversationState(),
        _default_planner(current_intent="price_objection", must_not_repeat=["individual_price"]),
    )
    assert res.failed and not res.checks["no_repeated_price"]

    # Without the price in answer → passes.
    res2 = validate_answer(
        "Да, индивидуально дороже. Если бюджет важен, группа — хороший старт.",
        ConversationState(),
        _default_planner(current_intent="price_objection", must_not_repeat=["individual_price"]),
    )
    assert not res2.failed


def test_comparison_intent_exempt_from_word_count() -> None:
    # compare_options is complex — a longer answer is not flagged.
    long_answer = " ".join(["Групповые"] * 130)
    res = validate_answer(long_answer, ConversationState(), _default_planner(current_intent="compare_options"))
    assert res.checks["compact_length_ok"] is True


def test_compact_mode_blocks_long_non_complex_answer() -> None:
    long_answer = " ".join(["Слово"] * 110)
    res = validate_answer(
        long_answer, ConversationState(), _default_planner(current_intent="answer_question")
    )
    assert res.failed and not res.checks["compact_length_ok"]


def test_long_bullet_list_only_allowed_for_ask_all_prices() -> None:
    five_bullets = (
        "• A: 39 000 ₸\n• B: 42 000 ₸\n• C: 45 000 ₸\n• D: 58 000 ₸\n• E: 9 500 ₸"
    )
    # Regular price intent → verbose list fails.
    res = validate_answer(five_bullets, ConversationState(), _default_planner(current_intent="ask_price"))
    assert res.failed and not res.checks["no_verbose_list"]
    # ask_all_prices → exempt.
    res2 = validate_answer(
        five_bullets, ConversationState(), _default_planner(current_intent="ask_all_prices")
    )
    assert res2.checks["no_verbose_list"] is True


def test_validator_triggers_repair_on_repeated_price_in_objection() -> None:
    history = [_msg("assistant", "Индивидуально — 9 500 ₸ за 60 минут, пакет из 8 — 72 000 ₸.")]
    gem = FakeGemini(
        planner=_default_planner(current_intent="price_objection", must_not_repeat=["individual_price"]),
        writer_texts=[
            "Понимаем. Индивидуальные занятия стоят 9 500 ₸ за урок.",  # repeats price → fails
            "Да, индивидуально дороже. Если бюджет важен, группа — хороший старт.",  # clean → passes
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("дороговато", history=history)))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True
    assert "9 500" not in resp.answer


def test_validator_triggers_repair_on_too_long_compact_answer() -> None:
    long_answer = " ".join(["Расскажем"] * 110)  # 110 words > _WORD_LIMIT
    gem = FakeGemini(
        planner=_default_planner(current_intent="answer_question"),
        writer_texts=[
            long_answer,  # too long → compact_length_ok fails
            "Коротко: занятия по английскому каждую неделю.",  # short → passes
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("расскажите о школе")))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True


# ---------------------------------------------------------------------------
# Fix 1–5: individual objection, clarification, CTA throttle, language, offensive
# ---------------------------------------------------------------------------

def test_individual_price_objection_not_handed_off() -> None:
    # "инд занятия почему такие дорогие" → price_objection, no contact, no handoff.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="price_objection",
            should_pause_qualification=True,
            slots={"format_preference": "individual"},
            must_not_repeat=["individual_price"],
            handoff_recommended=False,
            do_not_ask=["contact", "city", "level", "age"],
        ),
        writer_texts=[
            "Индивидуальные дороже, потому что формат один-на-один: весь урок с вами. "
            "Если бюджет важен, можно начать с мини-группы и решить после пробного урока.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("А инд занятия почему такие дорогие")))
    assert resp.metadata.get("handoff_recommended") is False
    low = resp.answer.casefold()
    assert "оставьте" not in low and "whatsapp" not in low
    assert "индивидуальн" in low or "один-на-один" in low or "форм" in low


def test_clarification_after_individual_objection_no_handoff() -> None:
    # "Я имею ввиду индивидуальные занятия" after price objection → correction, not handoff.
    history = [
        _msg("user", "А инд занятия почему такие дорогие"),
        _msg("assistant", "Индивидуальные дороже из-за формата один-на-один."),
    ]
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="correction",
            correction=True,
            should_pause_qualification=True,
            slots={"format_preference": "individual"},
            do_not_ask=["contact"],
            handoff_recommended=False,
        ),
        writer_texts=[
            "Да, понял — речь именно про индивидуальные. "
            "Они дороже из-за формата один-на-один: весь урок только с вами.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("Я имею ввиду индивидуальные занятия", history=history)))
    assert resp.metadata.get("handoff_recommended") is False
    low = resp.answer.casefold()
    assert "оставьте" not in low and "whatsapp" not in low


def test_turn_plan_suppresses_trial_cta_when_recently_mentioned() -> None:
    # When trial_cta_mentioned=True, offer_trial next step should be suppressed.
    state = ConversationState(trial_cta_mentioned=True)
    plan = build_turn_plan(
        state,
        _default_planner(recommended_next_step="offer_trial", should_pause_qualification=False),
    )
    # No "Следующий шаг" with trial hint — it was suppressed.
    assert "Следующий шаг" not in plan
    # But the "already mentioned" block must include it.
    assert "пробн" in plan.casefold()


def test_language_availability_question_answered_from_kb() -> None:
    # "А французский?" → ask_language_availability, no invented programs.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="ask_language_availability",
            question_to_answer="Есть ли программы по французскому?",
            should_pause_qualification=True,
        ),
        writer_texts=[
            "По материалам школы у нас программы по английскому. "
            "Французский в списке не вижу — лучше уточнить у администратора.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("А французский")))
    low = resp.answer.casefold()
    assert "французск" in low or "английск" in low
    assert "₸" not in resp.answer  # no invented French prices


def test_offensive_message_gets_calm_boundary() -> None:
    # Abusive message → calm boundary, no apology, no admin escalation.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="offensive",
            should_pause_qualification=True,
            do_not_ask=["contact"],
        ),
        writer_texts=[
            "Я могу помочь с вопросами по обучению в Alem English Academy. "
            "Если захотите продолжить по программам, ценам или пробному уроку — напишите.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("Пошел ты нахуй")))
    low = resp.answer.casefold()
    assert "извин" not in low
    assert "передам" not in low


def test_guardrail_blocks_contact_push_in_price_objection() -> None:
    # price_objection + do_not_ask=["contact"] + answer asks for contact → fails.
    res = validate_answer(
        "Хотите записаться на пробный урок? Оставьте имя и номер WhatsApp.",
        ConversationState(),
        _default_planner(current_intent="price_objection", do_not_ask=["contact"]),
    )
    assert res.failed and not res.checks["no_premature_contact_push"]

    # Objection answer without contact request → passes.
    res2 = validate_answer(
        "Да, индивидуально дороже. Если бюджет важен, группа — хороший старт.",
        ConversationState(),
        _default_planner(current_intent="price_objection", do_not_ask=["contact"]),
    )
    assert res2.checks.get("no_premature_contact_push") is True


# ---------------------------------------------------------------------------
# Round 5: promotion guardrail, competitor intent, individual objection, timeouts
# ---------------------------------------------------------------------------

def test_guardrail_blocks_installment_not_in_kb() -> None:
    # "рассрочка" is not in KB — guardrail must fail no_invented_promotion.
    res = validate_answer(
        "Оплата возможна в рассрочку на 3 месяца.",
        ConversationState(),
        _default_planner(),
    )
    assert res.failed and not res.checks["no_invented_promotion"]


def test_orchestrator_repairs_when_writer_invents_installment() -> None:
    # Writer invents installment plan → guardrail fires → repair returns clean answer.
    gem = FakeGemini(
        planner=_default_planner(),
        writer_texts=[
            "Оплата возможна в рассрочку на 3 месяца.",       # fails no_invented_promotion
            "Оплата принимается через Kaspi или банковской картой.",  # clean → passes
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("как оплатить?")))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True
    assert "рассрочку" not in resp.answer


def test_two_children_answer_prices_without_invented_discount() -> None:
    # For ages 8 and 15, correct answer gives prices for both children
    # and must not contain unsupported promotions.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="ask_price",
            slots={"student_age": "8 и 15", "user_role": "parent"},
        ),
        writer_texts=[
            "Для 8 лет — Kids English, 39 000 ₸/мес. "
            "Для 15 лет подходят Teen English (42 000 ₸/мес) или High School Speaking "
            "(45 000 ₸/мес) — зависит от цели. По семейной скидке уточните у администратора.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("двое детей, 8 и 15 лет, сколько?")))
    assert "39 000" in resp.answer
    assert "42 000" in resp.answer or "45 000" in resp.answer
    assert "рассрочк" not in resp.answer.casefold()
    assert resp.metadata["validation_result"]["checks"].get("no_invented_promotion") is True
    assert not resp.metadata["validation_result"]["failed"]


def test_compare_competitor_intent_in_orchestrator() -> None:
    # Planner returns compare_competitor → metadata reflects it, no handoff.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="compare_competitor",
            should_pause_qualification=True,
            handoff_recommended=False,
        ),
        writer_texts=[
            "Если сравнивать с 7 000 ₸ в другой школе, важно учесть формат: "
            "у нас мини-группы от 39 000 ₸/мес или индивидуально — 9 500 ₸/занятие. "
            "На пробном уроке можно сравнить подход.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("В другой школе стоит 7000 за час")))
    assert resp.metadata.get("current_intent") == "compare_competitor"
    assert resp.metadata.get("handoff_recommended") is False


def test_compare_competitor_answer_passes_guardrail() -> None:
    # A competitor comparison answer using only KB facts must pass all guardrails.
    answer = (
        "Если сравнивать с 7 000 ₸ в другой школе, важно учесть формат: "
        "у нас мини-группы от 39 000 ₸/мес или индивидуально — 9 500 ₸/занятие. "
        "На пробном уроке можно сравнить подход."
    )
    res = validate_answer(
        answer,
        ConversationState(),
        _default_planner(current_intent="compare_competitor"),
    )
    assert not res.failed, res.fix


def test_individual_objection_generic_filler_blocked() -> None:
    # "соотношение цены и качества" is a forbidden filler phrase — must fail no_filler.
    res = validate_answer(
        "Мы предлагаем наилучшее соотношение цены и качества в индивидуальных занятиях.",
        ConversationState(),
        _default_planner(current_intent="price_objection"),
    )
    assert res.failed and not res.checks["no_filler"]


def test_planner_timeout_returns_safe_response_no_crash() -> None:
    from unittest.mock import patch

    gem = FakeGemini(writer_texts=["Занятия от 39 000 ₸/мес."])

    async def _timeout(*args, **kwargs):
        raise asyncio.TimeoutError("simulated planner timeout")

    with patch("app.english_school_demo.plan_conversation_turn", side_effect=_timeout):
        resp = _run(handle_english_school_chat(gem, _request("сколько стоит?")))

    assert resp.answer
    assert resp.metadata.get("planner_timeout") is True
    assert resp.metadata.get("fallback_reason") == "planner_timeout"


def test_writer_timeout_returns_safe_fallback_no_crash() -> None:
    from unittest.mock import patch

    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"))

    async def _timeout(*args, **kwargs):
        raise asyncio.TimeoutError("simulated writer timeout")

    with patch("app.english_school_demo.write_response", side_effect=_timeout):
        resp = _run(handle_english_school_chat(gem, _request("сколько стоит?")))

    assert resp.answer
    assert "₸" not in resp.answer  # safe fallback has no invented prices
    assert resp.metadata.get("writer_timeout") is True
    assert resp.metadata.get("fallback_reason") == "writer_timeout"


def test_repair_timeout_returns_safe_fallback_no_crash() -> None:
    from unittest.mock import patch

    gem = FakeGemini(planner=_default_planner(current_intent="ask_price"))

    async def _timeout_on_repair(*args, repair=None, **kwargs):
        if repair:
            raise asyncio.TimeoutError("simulated repair timeout")
        return "Индивидуально стоит 100 000 ₸."  # invented price → triggers repair

    with patch("app.english_school_demo.write_response", side_effect=_timeout_on_repair):
        resp = _run(handle_english_school_chat(gem, _request("сколько стоит?")))

    assert resp.answer
    assert "100 000" not in resp.answer  # safe fallback used instead
    assert resp.metadata.get("repair_timeout") is True
    assert resp.metadata["repaired_answer"] is True


# ---------------------------------------------------------------------------
# General educational questions (ask_general_advice)
# ---------------------------------------------------------------------------

_ADMIN_FALLBACK_MARKER = "уточню точную информацию у администратора"


def test_reclassifier_turns_misfiled_timeline_question_into_general_advice() -> None:
    # Planner misfiles "за сколько ... уровень A2 -> B2" as ask_price with a
    # contact push — the deterministic net must retag it.
    plan = _default_planner(
        current_intent="ask_price",
        recommended_next_step="ask_contact",
        handoff_recommended=True,
    )
    out = reclassify_general_question("за сколько я смогу поднять уровень с А2 до Б2?", plan)
    assert out["current_intent"] == "ask_general_advice"
    assert out["handoff_recommended"] is False
    assert out["recommended_next_step"] == "none"


def test_reclassifier_fires_for_how_fast_phrasing() -> None:
    plan = _default_planner(current_intent="answer_question", handoff_recommended=True)
    out = reclassify_general_question("как быстро я смогу поднять уровень языка с А2 до Б2?", plan)
    assert out["current_intent"] == "ask_general_advice"
    assert out["handoff_recommended"] is False


def test_reclassifier_leaves_real_price_questions_alone() -> None:
    for msg in (
        "сколько стоит IELTS?",
        "сколько стоят индивидуальные занятия?",
        "за сколько тенге можно поднять уровень?",
        "что по ценам?",
    ):
        plan = reclassify_general_question(msg, _default_planner(current_intent="ask_price"))
        assert plan["current_intent"] == "ask_price", msg


def test_reclassifier_leaves_program_duration_company_specific() -> None:
    # Duration of a specific school program stays in the KB-protected lane
    # (no level/progress marker in the message).
    plan = reclassify_general_question(
        "за сколько месяцев можно пройти ваш курс IELTS Foundation?",
        _default_planner(current_intent="ask_program", handoff_recommended=True),
    )
    assert plan["current_intent"] == "ask_program"
    assert plan["handoff_recommended"] is True


def test_reclassifier_never_touches_protected_intents() -> None:
    for intent in ("price_objection", "contact", "wants_trial", "offensive", "correction"):
        plan = reclassify_general_question(
            "как быстро подниму уровень с A2 до B2?",
            _default_planner(current_intent=intent),
        )
        assert plan["current_intent"] == intent


def test_a2_b2_timeline_gets_general_answer_not_admin_fallback() -> None:
    general_answer = (
        "В среднем переход с A2 до B2 занимает примерно 9–18 месяцев при регулярных занятиях "
        "2–3 раза в неделю и домашней практике. Точный срок зависит от стартового уровня и "
        "регулярности. Хотите, подберём программу после короткой диагностики?"
    )
    # Planner misclassifies as ask_price — without the fix the price guardrail
    # would reject this answer (no ₸) and force the admin fallback.
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price", handoff_recommended=True),
        writer_texts=[general_answer],
    )
    resp = _run(handle_english_school_chat(gem, _request("за сколько я смогу поднять уровень с А2 до Б2?")))
    assert resp.metadata["current_intent"] == "ask_general_advice"
    assert resp.answer == general_answer
    assert gem.writer_calls == 1  # no repair needed
    assert _ADMIN_FALLBACK_MARKER not in resp.answer


def test_repeated_a2_b2_question_does_not_repeat_admin_fallback() -> None:
    from app.english_school_guardrails import _FALLBACK_PRICE_FORMAT

    history = [
        _msg("user", "за сколько я смогу поднять уровень с А2 до Б2?"),
        _msg("assistant", _FALLBACK_PRICE_FORMAT),  # the old bad turn
    ]
    general_answer = (
        "Обычно переход с A2 до B2 занимает 9–18 месяцев при занятиях 2–3 раза в неделю. "
        "Точнее скажем после короткой диагностики уровня."
    )
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_price"),
        writer_texts=[general_answer],
    )
    resp = _run(handle_english_school_chat(
        gem, _request("как быстро я смогу поднять уровень языка с А2 до Б2?", history=history)
    ))
    assert resp.answer == general_answer
    assert _ADMIN_FALLBACK_MARKER not in resp.answer


def test_speaking_advice_question_gets_useful_answer() -> None:
    advice = (
        "Барьер обычно уходит с регулярной разговорной практикой: короткие сессии 2–3 раза в "
        "неделю, простые темы, без страха ошибок. Помогает и разговорный клуб — там тренируют "
        "именно живое общение. Хотите, расскажу про наш Speaking Club?"
    )
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_general_advice"),
        writer_texts=[advice],
    )
    resp = _run(handle_english_school_chat(gem, _request("как перестать бояться говорить на английском?")))
    assert resp.answer == advice
    assert resp.metadata["validation_result"]["failed"] is False
    assert resp.metadata.get("handoff_recommended") is False


def test_general_advice_still_cannot_invent_prices() -> None:
    res = validate_answer(
        "Обычно это занимает около года. Кстати, наш курс стоит 100 000 ₸ в месяц.",
        ConversationState(),
        _default_planner(current_intent="ask_general_advice"),
    )
    assert res.failed and not res.checks["no_invented_prices"]


def test_general_advice_can_mention_real_kb_prices() -> None:
    res = validate_answer(
        "Регулярная разговорная практика решает. У нас для этого есть Speaking Club — 15 000 ₸/мес.",
        ConversationState(),
        _default_planner(current_intent="ask_general_advice"),
    )
    assert res.checks["no_invented_prices"] is True


def test_general_advice_still_cannot_invent_promotions() -> None:
    res = validate_answer(
        "Можно ускориться: оформите рассрочку и получите скидку 30%.",
        ConversationState(),
        _default_planner(current_intent="ask_general_advice"),
    )
    assert res.failed and not res.checks["no_invented_promotion"]


def test_general_advice_still_cannot_guarantee_results() -> None:
    res = validate_answer(
        "Гарантируем уровень B2 за 6 месяцев занятий.",
        ConversationState(),
        _default_planner(current_intent="ask_general_advice"),
    )
    assert res.failed and not res.checks["no_guarantees"]


def test_general_advice_exempt_from_word_limit_but_not_lists() -> None:
    long_answer = " ".join(["совет"] * 130)
    res = validate_answer(
        long_answer, ConversationState(), _default_planner(current_intent="ask_general_advice")
    )
    assert res.checks["compact_length_ok"] is True
    # Bullet-list compactness still applies.
    bullets = "• раз\n• два\n• три\n• четыре\n• пять"
    res2 = validate_answer(
        bullets, ConversationState(), _default_planner(current_intent="ask_general_advice")
    )
    assert res2.failed and not res2.checks["no_verbose_list"]


def test_safe_fallback_for_general_advice_has_no_admin_or_contact_push() -> None:
    fb = build_safe_fallback(_default_planner(current_intent="ask_general_advice"))
    low = fb.casefold()
    assert "администратор" not in low
    assert "whatsapp" not in low and "telegram" not in low and "оставьте" not in low
    assert "₸" not in fb
    # The fallback itself passes the guardrail.
    res = validate_answer(fb, ConversationState(), _default_planner(current_intent="ask_general_advice"))
    assert not res.failed, res.fix


# ---------------------------------------------------------------------------
# Round 6: adult contact, contact-aware fallbacks, booking, format, greeting
# ---------------------------------------------------------------------------

def test_guardrail_rejects_child_contact_request() -> None:
    # "его имя и номер телефона" after "хочу внука записать" — must fail.
    res = validate_answer(
        "Отлично! Чтобы записать внука, мне понадобится его имя и номер телефона в WhatsApp или Telegram.",
        ConversationState(),
        _default_planner(current_intent="wants_trial"),
    )
    assert res.failed and not res.checks["no_child_contact_request"]


def test_guardrail_accepts_adult_contact_request() -> None:
    res = validate_answer(
        "Оставьте, пожалуйста, ваше имя и WhatsApp/Telegram для связи.",
        ConversationState(),
        _default_planner(current_intent="wants_trial"),
    )
    assert res.checks["no_child_contact_request"] is True
    assert not res.failed, res.fix


def test_orchestrator_repairs_child_contact_wording() -> None:
    gem = FakeGemini(
        planner=_default_planner(current_intent="wants_trial", recommended_next_step="ask_contact"),
        writer_texts=[
            "Отлично! Мне понадобится его имя и номер телефона в WhatsApp.",  # child contact → fails
            "Отлично! Оставьте, пожалуйста, ваше имя и WhatsApp/Telegram для связи.",  # adult → passes
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("Хорошо. Я хочу внука записать")))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True
    low = resp.answer.casefold()
    assert "его имя" not in low and "его номер" not in low
    assert "ваше имя" in low


def test_no_contact_reask_after_phone_provided() -> None:
    # Even when the writer keeps re-asking for the contact and the safe fallback
    # kicks in, the final answer must NOT ask for the contact again.
    history = [
        _msg("user", "Хочу записать внука"),
        _msg("assistant", "Оставьте, пожалуйста, ваше имя и WhatsApp/Telegram для связи."),
    ]
    gem = FakeGemini(
        planner=_default_planner(current_intent="contact"),
        writer_texts=[
            "Оставьте, пожалуйста, имя и номер WhatsApp или Telegram.",  # re-asks → fails
            "Хорошо! Оставьте ваш контакт для связи.",                    # still re-asks → fails
        ],
    )
    resp = _run(handle_english_school_chat(
        gem, _request("запишите внука на ближайший урок +7777282882", history=history)
    ))
    low = resp.answer.casefold()
    assert "оставьте" not in low
    assert "администратор" in low
    assert resp.lead_status == "contact_collected"


def test_booking_with_phone_acknowledged_and_routed_to_admin() -> None:
    good = (
        "Спасибо, номер записала! Заявка принята — администратор свяжется с вами и предложит "
        "ближайшее доступное время пробного урока. Подскажите, как к вам обращаться и сколько лет внуку?"
    )
    gem = FakeGemini(
        planner=_default_planner(current_intent="contact", slots={"user_role": "parent"}),
        writer_texts=[good],
    )
    resp = _run(handle_english_school_chat(gem, _request("запишите внука на ближайший урок +7777282882")))
    assert resp.answer == good
    assert resp.metadata["validation_result"]["failed"] is False
    assert resp.lead_status == "contact_collected"


def test_guardrail_blocks_invented_availability() -> None:
    # The bot must not confirm a slot or claim free places — admin's job.
    res = validate_answer(
        "Отлично, записал вас на завтра в 15:00 — есть свободное место в группе.",
        ConversationState(),
        _default_planner(current_intent="wants_trial"),
    )
    assert res.failed and not res.checks["no_invented_availability"]

    res2 = validate_answer(
        "Заявка принята — администратор подтвердит ближайшее доступное время пробного урока.",
        ConversationState(),
        _default_planner(current_intent="wants_trial"),
    )
    assert res2.checks["no_invented_availability"] is True


def test_format_not_confirmed_from_competitor_price_comparison() -> None:
    state = ConversationState()
    apply_planner_updates(
        state,
        _default_planner(current_intent="compare_competitor", slots={"format_preference": "individual"}),
    )
    assert state.format_preference == "unknown"


def test_format_not_confirmed_from_price_objection() -> None:
    state = ConversationState()
    apply_planner_updates(
        state,
        _default_planner(current_intent="price_objection", slots={"format_preference": "individual"}),
    )
    assert state.format_preference == "unknown"


def test_format_still_set_on_explicit_choice() -> None:
    state = ConversationState()
    apply_planner_updates(
        state,
        _default_planner(current_intent="wants_trial", slots={"format_preference": "individual"}),
    )
    assert state.format_preference == "individual"


def test_price_objection_fallback_is_commercial_not_generic() -> None:
    fb = build_safe_fallback(_default_planner(current_intent="price_objection"))
    low = fb.casefold()
    assert "мини-групп" in low and "пробн" in low
    assert "₸" not in fb and "гаранти" not in low
    assert "точный результат" not in low  # old generic deflection
    # It must pass the guardrail even with a price-repeat ban active.
    res = validate_answer(
        fb, ConversationState(),
        _default_planner(current_intent="price_objection", must_not_repeat=["individual_price"]),
    )
    assert not res.failed, res.fix


def test_competitor_price_objection_falls_back_commercially() -> None:
    # Writer keeps repeating a banned price → safe fallback must be the
    # commercial objection answer, not the generic "результат зависит..." text.
    history = [_msg("assistant", "Индивидуально — 9 500 ₸ за 60 минут, пакет из 8 — 72 000 ₸.")]
    gem = FakeGemini(
        planner=_default_planner(current_intent="compare_competitor", must_not_repeat=["individual_price"]),
        writer_texts=[
            "Индивидуально у нас 9 500 ₸ — это лучше, чем 7000.",
            "Наши занятия стоят 9 500 ₸, зато качество выше.",
        ],
    )
    resp = _run(handle_english_school_chat(
        gem, _request("Чё так дорого? У меня возле дома инд стоит 7000", history=history)
    ))
    assert "9 500" not in resp.answer
    low = resp.answer.casefold()
    assert "мини-групп" in low
    assert "точный результат" not in low


def test_guardrail_rejects_repeated_greeting_mid_conversation() -> None:
    state = ConversationState(greeting_already_sent=True)
    res = validate_answer(
        "Здравствуйте! Стоимость зависит от программы — групповые от 39 000 ₸ в месяц.",
        state,
        _default_planner(current_intent="ask_relevant_price"),
    )
    assert res.failed and not res.checks["no_repeated_greeting"]


def test_greeting_allowed_on_first_turn() -> None:
    res = validate_answer(
        "Здравствуйте! Расскажу о программах школы.",
        ConversationState(),  # greeting_already_sent=False → check not applied
        _default_planner(),
    )
    assert res.checks.get("no_repeated_greeting") is None
    assert not res.failed, res.fix


def test_build_state_sets_greeting_flag() -> None:
    history = [
        _msg("assistant", "Здравствуйте! Я помощник Alem English Academy."),
        _msg("user", "привет"),
    ]
    assert build_conversation_state(history, "Сколько стоит?").greeting_already_sent is True
    assert build_conversation_state([], "привет").greeting_already_sent is False


def test_orchestrator_repairs_repeated_greeting() -> None:
    history = [
        _msg("assistant", "Здравствуйте! Я помощник Alem English Academy. Чем могу помочь?"),
        _msg("user", "Хочу внука записать"),
        _msg("assistant", "Подскажите, сколько лет внуку?"),
    ]
    gem = FakeGemini(
        planner=_default_planner(current_intent="ask_relevant_price"),
        writer_texts=[
            "Здравствуйте! Групповые занятия стоят от 39 000 ₸ в месяц.",  # greets again → fails
            "Групповые занятия стоят от 39 000 ₸ в месяц, индивидуальные — 9 500 ₸ за занятие.",
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("Сколько будет стоить?", history=history)))
    assert gem.writer_calls == 2
    assert not resp.answer.casefold().startswith("здравствуйте")
    assert "39 000" in resp.answer


def test_turn_plan_contains_contact_received_rule() -> None:
    state = ConversationState(contact="+7777282882")
    plan = build_turn_plan(
        state,
        _default_planner(current_intent="contact", recommended_next_step="ask_contact"),
    )
    assert "КОНТАКТ УЖЕ ПОЛУЧЕН" in plan
    assert "Следующий шаг" not in plan  # ask_contact suppressed for known contact


def test_safe_fallback_contact_aware() -> None:
    state = ConversationState(contact="+7777282882")
    for intent in ("contact", "wants_trial", "ask_price", "smalltalk"):
        fb = build_safe_fallback(_default_planner(current_intent=intent), state)
        low = fb.casefold()
        assert "оставьте" not in low, intent
        assert "имя и номер" not in low, intent
    # Age/name details asked only for a parent with unknown student age.
    parent = ConversationState(contact="+7777282882", user_role="parent")
    fb = build_safe_fallback(_default_planner(current_intent="wants_trial"), parent)
    assert "сколько лет" in fb.casefold()
    parent_with_age = ConversationState(contact="+7777282882", user_role="parent", student_age="10")
    fb2 = build_safe_fallback(_default_planner(current_intent="wants_trial"), parent_with_age)
    assert "сколько лет" not in fb2.casefold()


def test_orchestrator_repairs_when_writer_violates_do_not_ask_location() -> None:
    # Planner knows the district and forbids asking it again; the writer still asks.
    # The guardrail must catch it and the repair must fix it.
    gem = FakeGemini(
        planner=_default_planner(
            current_intent="correction",
            correction=True,
            do_not_ask=["district_or_branch"],
            slots={"preferred_location_text": "Турана"},
        ),
        writer_texts=[
            "Хорошо. А в каком районе ближайшего филиала будете заниматься?",  # violates -> fails
            "Да, вы правы — это Турана. Тогда подберём удобное время для пробного урока.",  # clean
        ],
    )
    resp = _run(handle_english_school_chat(gem, _request("я же сказал на турана")))
    assert gem.writer_calls == 2
    assert resp.metadata["repaired_answer"] is True
    assert resp.metadata["state"]["preferred_location_text"] == "Турана"
    # The final answer no longer asks a district/location question.
    assert resp.metadata["validation_result"]["checks"]["no_repeated_known_slot"] is True
