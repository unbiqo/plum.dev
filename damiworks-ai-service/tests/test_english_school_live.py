"""Opt-in LIVE eval suite for the English School demo.

These call the REAL Gemini API and assert on actual answers. They are skipped
unless ``RUN_LIVE_EVALS=1`` and the configured Gemini API keys are available, so
the default CI run (``test_english_school_demo.py``) stays fast and key-free.

Run locally:
    RUN_LIVE_EVALS=1 python -m pytest tests/test_english_school_live.py -q

The scenarios replay the real failing dialogue and the spec scenarios:
latest intent answered first, no stale district re-ask, no crash on the
individual-price turn, known slots preserved, prices grounded in the KB.
"""

from __future__ import annotations

import asyncio
import os
import re

import pytest

from app.english_school_demo import ENGLISH_SCHOOL_INSTANCE_ID, handle_english_school_chat
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


def _h(*pairs: tuple[str, str]) -> list[ChatHistoryMessage]:
    return [ChatHistoryMessage(role=r, content=c) for r, c in pairs]


def _ask(gemini, message: str, history: list[ChatHistoryMessage]):
    req = ChatRequest(
        channel="web_site",
        chat_id="live-eval",
        instance_id=ENGLISH_SCHOOL_INSTANCE_ID,
        message=message,
        chat_history=history,
    )
    return asyncio.run(handle_english_school_chat(gemini, req))


_LOCATION_CUES = ("район", "филиал", "локац", "адрес", "из них", "где вам", "где удобнее")


def _asks_district(answer: str) -> bool:
    """True only if an interrogative *sentence* asks about district/branch/location.

    A factual mention like "…в районе Турана, офлайн." (no question) does not count —
    only a question sentence (ending in '?') that references a location does.
    """
    for sentence in re.split(r"(?<=[.!?])\s+", answer):
        low = sentence.casefold().strip()
        if low.endswith("?") and any(cue in low for cue in _LOCATION_CUES):
            return True
    return False


# The actual reported bad dialogue, replayed turn by turn.
_BAD_DIALOGUE = _h(
    ("assistant", "Здравствуйте! Подскажу по программам Alem English Academy. Что вас интересует?"),
    ("user", "у меня есть ребенок, который будет сдавать айлтс через год. хотим начать готовиться"),
    ("assistant", "Отлично! В каком городе удобнее заниматься?"),
    ("user", "Астана. А сколько стоит?"),
    ("assistant", "Группа IELTS Foundation — 58 000 ₸/мес за 12 занятий. Какой район Астаны удобнее?"),
    ("user", "это занятия в группах или индивидуально?"),
    ("assistant", "IELTS Foundation — это групповой курс. Индивидуальные занятия тоже есть."),
    ("user", "а есть индивидуальные занятия?"),
    ("assistant", "Да, индивидуальные занятия есть."),
)


def test_individual_price_turn_does_not_crash_and_quotes_kb(gemini):
    resp = _ask(gemini, "а сколько стоят индивидуальные занятия?", _BAD_DIALOGUE)
    assert resp.answer  # no crash / no empty answer
    assert "error" not in resp.metadata
    assert "9 500" in resp.answer or "9500" in resp.answer
    assert not _asks_district(resp.answer)


def test_price_after_city_answers_price_not_district(gemini):
    history = _h(
        ("assistant", "В каком городе удобнее заниматься?"),
        ("user", "у меня ребенок, IELTS через год"),
        ("assistant", "Отлично! В каком городе удобнее?"),
    )
    resp = _ask(gemini, "Астана. А сколько стоит?", history)
    assert any(p in resp.answer for p in ("58 000", "58000", "₸"))
    assert not _asks_district(resp.answer)
    assert resp.metadata.get("current_intent") in ("ask_price", "ask_relevant_price", "answer_question")
    assert resp.metadata.get("should_pause_qualification") is True


def test_format_comparison_mentions_both(gemini):
    resp = _ask(gemini, "это занятия в группах или индивидуально?", _BAD_DIALOGUE[:5])
    low = resp.answer.casefold()
    assert "групп" in low and "индивидуальн" in low
    assert not _asks_district(resp.answer)


def test_individual_availability_proactively_mentions_price(gemini):
    resp = _ask(gemini, "а есть индивидуальные занятия?", _BAD_DIALOGUE[:7])
    assert "9 500" in resp.answer or "9500" in resp.answer


def test_district_free_text_is_not_reasked(gemini):
    history = _h(
        ("user", "хочу IELTS в Астане офлайн"),
        ("assistant", "Хорошо. Какой район или филиал удобнее?"),
    )
    resp = _ask(gemini, "турана", history)
    assert not _asks_district(resp.answer)


def test_correction_is_acknowledged_without_reasking(gemini):
    history = _h(
        ("user", "IELTS в Астане офлайн"),
        ("assistant", "Какой район удобнее?"),
        ("user", "турана"),
        ("assistant", "Какой район удобнее?"),
    )
    resp = _ask(gemini, "я же сказал на турана", history)
    assert not _asks_district(resp.answer)
