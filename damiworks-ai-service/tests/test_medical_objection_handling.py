"""Objection-handling contract for the Medical Center demo (offline).

Golden fixture: the real live test dialog (chat 7e0bbd54, 2026-07-20) where the
bot behaved like a reference desk instead of an administrator: it surrendered
after the first "no" («Мы всегда рады видеть вас» three times), re-asked the
complaint stated in the very first message, and answered the guarantee question
with the meta fallback («подберём безопасный шаг»). Root causes pinned here:

1. The writer/planner saw only a truncated history window, so the anti-repeat
   and no-re-asking rules had nothing to work with -> full history now.
2. The guarantee guardrail treated an honest "no guarantees" DISCLAIMER the
   same as giving a guarantee, so every honest answer was replaced by the meta
   fallback -> disclaimers are scrubbed before the check.
3. The prompt had no objection scheme and suppressed repeat booking CTAs
   entirely -> scheme: признать -> аргумент из базы -> один шаг к записи;
   сдача только после третьего подряд отказа.

The live replay of the same dialog lives in test_medical_objection_live.py
(RUN_LIVE_EVALS=1, -m live).
"""

from __future__ import annotations

import asyncio
import json

from app.config import MODEL_PROFILES, GeminiApiKey, Settings
from app.gemini_service import GeminiService
from app.medical_center_guardrails import build_safe_fallback, validate_answer
from app.medical_center_state import build_conversation_state
from app.medical_center_writer import _WRITER_SYSTEM, build_turn_plan, write_response
from app.schemas import ChatHistoryMessage


def _run(coro):
    return asyncio.run(coro)


# The real dialog, verbatim from ai_conversation_messages (trimmed answers).
GOLDEN_DIALOG: list[tuple[str, str]] = [
    ("user", "Здравствуйте, у меня зрение просело"),
    ("assistant", "С этой проблемой вам поможет офтальмолог. В нашей клинике ведет прием "
                  "Ольга Панченко, она принимает взрослых и детей от 6 лет. Стоимость "
                  "первичного приема составляет 11 500 ₸.\n\nСколько лет пациенту?"),
    ("user", "23. Дороговато что-то. У другой клиники за 9"),
    ("assistant", "Понимаю, что вопрос цены важен. Ольга Панченко, врач первой категории с "
                  "7-летним стажем, а в стоимость приема уже включена профессиональная "
                  "диагностика, включая проверку глазного дна. Если решите записаться, дайте знать"),
    ("user", "В той клинике тоже самое предлагают"),
    ("assistant", "Выбор клиники это всегда ваше право. В MedNova мы делаем упор на комплексный "
                  "подход и опыт наших специалистов.\n\nМы всегда рады видеть вас в MedNova."),
    ("user", "Понятно, вам нечего сказать"),
    ("assistant", "Мы уважаем ваш выбор и всегда будем рады видеть вас, если в будущем решите "
                  "обратиться в нашу клинику."),
    ("assistant", "Мы всегда будем рады видеть вас в MedNova, если решите записаться."),
    ("user", "Мне нужно подумать"),
    ("user", "Вы просто назначаете лишние анализы и процедуры, чтобы выкачать деньги"),
    ("assistant", "В MedNova врачи придерживаются принципов доказательной медицины. Все назначения "
                  "обоснованы клиническими протоколами для постановки точного диагноза."),
    ("user", "Зачем мне идти платно, если придется всё равно ждать в очереди"),
    ("assistant", "Мы стремимся к тому, чтобы прием проходил строго по записи, что позволяет "
                  "минимизировать время ожидания для наших пациентов."),
    ("user", "А вы гарантируете, что это точно поможет и не будет осложнений?"),
    ("assistant", "Понимаю вопрос. Давайте подберём безопасный следующий шаг — могу подсказать "
                  "направление или передать вопрос администратору."),
    ("user", "Окей"),
    ("assistant", "Мы работаем по предварительной записи, чтобы прием проходил комфортно и без "
                  "очередей.\n\nЧто именно вас беспокоит?"),
    ("user", "Я же говорил"),
    ("assistant", "Мы ценим обратную связь и стремимся к качественному обслуживанию."),
]


def _golden_history() -> list[ChatHistoryMessage]:
    return [ChatHistoryMessage(role=r, content=c) for r, c in GOLDEN_DIALOG]


def _planner(**overrides) -> dict:
    plan = {
        "current_intent": "answer_question",
        "intent_priority": "high",
        "should_pause_qualification": False,
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


def _make_service() -> GeminiService:
    settings = Settings(
        gemini_api_keys=(GeminiApiKey("TEST", "fake-key"),),
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="fake",
        model_profiles=dict(MODEL_PROFILES),
    )
    return GeminiService(settings)


# ---------------------------------------------------------------------------
# 1. Full history reaches the writer (the 15-message window dropped the
#    opening complaint of the 20-message golden dialog).
# ---------------------------------------------------------------------------

def test_medical_writer_receives_the_full_golden_dialog() -> None:
    svc = _make_service()
    captured: dict[str, str] = {}

    async def fake_generate_text(**kw):
        captured["prompt"] = kw.get("prompt") or ""
        return "ок"

    svc._generate_text = fake_generate_text

    history = _golden_history()
    message = "А вы гарантируете, что это точно поможет?"
    state = build_conversation_state(history, message)
    _run(write_response(message, history, state, _planner(), "kb", svc))

    # First message of the dialog (outside the old 15-message window)…
    assert "зрение просело" in captured["prompt"]
    # …and a mid-dialog objection are both visible to the writer.
    assert "выкачать деньги" in captured["prompt"]


# ---------------------------------------------------------------------------
# 2. Writer system prompt: administrator, not a reference desk.
# ---------------------------------------------------------------------------

def test_writer_system_has_the_objection_scheme() -> None:
    low = _WRITER_SYSTEM.lower()
    assert "работа с возражениями" in low
    # признать -> аргумент из базы -> один шаг; сдача только после 3-го отказа.
    assert "признай возражение" in low
    assert "содержательный аргумент строго из базы знаний" in low
    assert "третий раз подряд" in low
    # Запрет повторов и переспрашивания известного.
    assert "не используй формулировку, которая уже звучала" in low
    assert "не переспрашивай то, что клиент уже сообщил" in low


def test_writer_system_answers_guarantee_questions_honestly() -> None:
    low = _WRITER_SYSTEM.lower()
    assert "гарантий результата в медицине не даёт" in low
    assert "первичный" in low  # предложение первичного приёма
    assert "подберём безопасный шаг" in low  # named as a FORBIDDEN meta phrase


def test_writer_system_no_longer_suppresses_selling() -> None:
    low = _WRITER_SYSTEM.lower()
    # The old suppressor: "Не предлагай запись… CTA уместен, когда пользователь
    # показал интерес" — gone; every answer moves one soft step toward booking.
    assert "cta уместен" not in low
    assert "движение к записи" in low


# ---------------------------------------------------------------------------
# 3. Turn plan: objection scheme injected, booking CTA not silenced.
# ---------------------------------------------------------------------------

def test_turn_plan_injects_objection_scheme_for_objection_intents() -> None:
    history = _golden_history()
    state = build_conversation_state(history, "Дороговато")
    for intent in ("objection", "price_objection"):
        plan_text = build_turn_plan(state, _planner(current_intent=intent))
        assert "Возражение:" in plan_text, intent
        assert "аргумент" in plan_text, intent
        assert "шаг к записи" in plan_text, intent
    neutral = build_turn_plan(state, _planner(current_intent="answer_question"))
    assert "Возражение:" not in neutral


def test_offer_booking_step_survives_an_earlier_cta() -> None:
    # Regression: state.booking_cta_mentioned used to turn offer_booking into
    # "none", which produced dead-end answers («Если решите записаться, дайте
    # знать»). Now the step stays; only the wording must change.
    state = build_conversation_state([], "ну не знаю")
    state.booking_cta_mentioned = True
    plan_text = build_turn_plan(
        state, _planner(current_intent="objection", recommended_next_step="offer_booking")
    )
    assert "предложи записаться" in plan_text


# ---------------------------------------------------------------------------
# 4. Guarantee guardrail: honest disclaimers pass, promises still fail.
# ---------------------------------------------------------------------------

def test_honest_no_guarantee_answer_passes_the_guardrail() -> None:
    state = build_conversation_state([], "а вы гарантируете?")
    answer = (
        "Гарантий результата в медицине не даёт ни одна добросовестная клиника. "
        "Приём ведёт врач первой категории, на осмотре он честно скажет, что нужно.\n\n"
        "Хотите, покажу ближайшие окна?"
    )
    result = validate_answer(answer, state, _planner(current_intent="objection"))
    assert result.checks["no_guarantees"] is True


def test_more_disclaimer_shapes_pass_the_guardrail() -> None:
    state = build_conversation_state([], "а вы гарантируете?")
    for answer in (
        "Не могу гарантировать результат, это решает врач на приёме.",
        "Мы не даём никаких гарантий результата, но врач честно оценит ситуацию.",
        "Честно: стопроцентных гарантий не бывает, итог зависит от осмотра.",
    ):
        result = validate_answer(answer, state, _planner(current_intent="objection"))
        assert result.checks["no_guarantees"] is True, answer


def test_affirmative_guarantees_still_fail_the_guardrail() -> None:
    state = build_conversation_state([], "а вы гарантируете?")
    for answer in (
        "Гарантируем результат, вы останетесь довольны.",
        "Процедура точно поможет, не переживайте.",
        "Успех на 100 %, у нас лучшие врачи.",
        # A promise next to a disclaimer is still a promise.
        "Мы не даём гарантий на бумаге, но гарантируем, что всё пройдет отлично.",
    ):
        result = validate_answer(answer, state, _planner(current_intent="objection"))
        assert result.checks["no_guarantees"] is False, answer


# ---------------------------------------------------------------------------
# 5. Objection fallback: human wording, argument + a step toward booking.
# ---------------------------------------------------------------------------

def test_objection_fallback_moves_to_booking_without_meta_language() -> None:
    for intent in ("objection", "price_objection", "correction"):
        fallback = build_safe_fallback(_planner(current_intent=intent))
        assert "безопасный шаг" not in fallback, intent
        assert "окна" in fallback, intent           # конкретный следующий шаг
        assert fallback.rstrip().endswith("?"), intent
        # The fallback itself passes its own guardrails.
        state = build_conversation_state([], "дорого")
        result = validate_answer(fallback, state, _planner(current_intent=intent))
        assert not result.failed, (intent, result.fix)
