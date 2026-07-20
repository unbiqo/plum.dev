"""Opt-in LIVE replay of the golden objection dialog (Medical Center demo).

Calls the REAL LLM pipeline and asserts the objection-handling contract on the
actual answers: every objection gets an argument plus a step toward booking, no
verbatim phrase repeats, no re-asking what the client already said, and the
guarantee question gets a human answer instead of the meta fallback.

Run locally:
    RUN_LIVE_EVALS=1 python -m pytest tests/test_medical_objection_live.py -q
"""

from __future__ import annotations

import asyncio
import os
import re

import pytest

from app.medical_center_demo import MEDICAL_CENTER_INSTANCE_ID, handle_medical_center_chat
from app.schemas import ChatHistoryMessage, ChatRequest

pytestmark = pytest.mark.live

if os.getenv("RUN_LIVE_EVALS") != "1":
    pytest.skip("live evals disabled (set RUN_LIVE_EVALS=1)", allow_module_level=True)


@pytest.fixture(scope="module")
def gemini():
    from app.config import get_settings
    from app.gemini_service import GeminiService

    settings = get_settings()
    if not getattr(settings, "gemini_api_keys", None):
        pytest.skip("no Gemini API keys configured")
    return GeminiService(settings)


# The golden dialog's user turns: price objection, competitor, "подумаю",
# distrust ("выкачиваете деньги"), queue, guarantee.
GOLDEN_USER_TURNS = [
    "Здравствуйте, у меня зрение просело",
    "23. Дороговато что-то. У другой клиники за 9",
    "В той клинике тоже самое предлагают",
    "Мне нужно подумать",
    "Вы просто назначаете лишние анализы и процедуры, чтобы выкачать деньги",
    "Зачем мне идти платно, если придется всё равно ждать в очереди",
    "А вы гарантируете, что это точно поможет и не будет осложнений?",
]

# Farewell/give-up lines are allowed only after a third consecutive refusal —
# never in this dialog (the user keeps asking questions, not refusing thrice).
_GIVE_UP_RE = re.compile(
    r"всегда\s+(?:будем\s+)?рады\s+видеть|ваше\s+право|если\s+решите", re.IGNORECASE
)
_ASKS_AGE_RE = re.compile(r"сколько\s+(?:вам\s+)?лет", re.IGNORECASE)


def _sentences(text: str) -> list[str]:
    return [
        s.strip().casefold()
        for s in re.split(r"(?<=[.!?])\s+", text or "")
        if len(s.strip()) > 15
    ]


def _has_next_step(answer: str) -> bool:
    low = (answer or "").casefold()
    return "?" in answer or "запис" in low or "окн" in low


@pytest.fixture(scope="module")
def golden_replay(gemini):
    """Drive the real pipeline over the golden turns; return per-turn answers."""
    history: list[ChatHistoryMessage] = []
    answers: list[str] = []
    for turn in GOLDEN_USER_TURNS:
        req = ChatRequest(
            channel="web_site",
            chat_id="live-objection-eval",
            instance_id=MEDICAL_CENTER_INSTANCE_ID,
            message=turn,
            chat_history=list(history),
        )
        response = asyncio.run(handle_medical_center_chat(gemini, req))
        answers.append(response.answer)
        history.append(ChatHistoryMessage(role="user", content=turn))
        history.append(ChatHistoryMessage(role="assistant", content=response.answer))
    return answers


def test_objections_get_an_argument_and_a_step_not_a_farewell(golden_replay) -> None:
    # Turns 1..5 are objections; none may surrender or dead-end.
    for index in range(1, 6):
        answer = golden_replay[index]
        assert not _GIVE_UP_RE.search(answer), (index, answer)
        assert _has_next_step(answer), (index, answer)


def test_no_verbatim_phrase_repeats_across_the_dialog(golden_replay) -> None:
    seen: set[str] = set()
    for answer in golden_replay:
        for sentence in _sentences(answer):
            assert sentence not in seen, sentence
            seen.add(sentence)


def test_age_is_never_re_asked_after_the_user_gave_it(golden_replay) -> None:
    # The user answered "23" in turn 2; later answers must not re-ask it.
    for answer in golden_replay[2:]:
        assert not _ASKS_AGE_RE.search(answer), answer


def test_guarantee_question_gets_a_human_answer(golden_replay) -> None:
    answer = golden_replay[6]
    assert "безопасный шаг" not in answer.casefold()
    # Honest no-guarantee + a concrete step (first visit / slots / booking).
    assert _has_next_step(answer), answer
    assert "гарант" in answer.casefold(), answer
