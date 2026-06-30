"""Tests for DamiWorks Discovery-mode price hiding.

Verifies that when HIDE_DAMIWORKS_PUBLIC_PRICES=True:
- Pre-intake FAQ price answer contains no ₸ amounts
- Post-intake price_question_answer contains no ₸ amounts
- price_objection_answer contains no ₸ amounts
- cheaper_answer contains no ₸ amounts
- business_details_answer contains no ₸ amounts
- _sanitize_damiworks_web_answer strips ₸ amounts that slip through LLM

None of these touch English School or Custom Demo.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from app.web_site_intake_policy import (
    HIDE_DAMIWORKS_PUBLIC_PRICES,
    business_details_answer,
    cheaper_answer,
    pre_intake_faq_answer,
    price_objection_answer,
    price_question_answer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Pattern that matches any of the exact DamiWorks package price amounts.
_PRICE_RE = re.compile(
    r"\b(?:150\s*000|200\s*000|350\s*000|700\s*000|40\s*000|60\s*000|120\s*000)"
    r"(?:\s*[–—\-]\s*(?:200\s*000|60\s*000))?"
    r"\s*₸",
    re.IGNORECASE,
)


def _has_price(text: str) -> bool:
    return bool(_PRICE_RE.search(text))


def _make_ctx(
    recommended_package: str = "Sales Assistant",
    channels: list[str] | None = None,
    tasks: list[str] | None = None,
    shown_price: str = "от 350 000 ₸",
) -> MagicMock:
    ctx = MagicMock()
    ctx.recommended_package = recommended_package
    ctx.channels = channels or ["WhatsApp"]
    ctx.tasks = tasks or ["Ответы на вопросы", "Передавать заявки менеджеру"]
    ctx.business_type = "Услуги"
    ctx.handoff = "Google Sheets"
    ctx.volume = "10–30"
    ctx.timeline = "В ближайшие дни"
    ctx.shown_price = shown_price
    ctx.exists = True
    return ctx


# ---------------------------------------------------------------------------
# Guard: the constant must actually be True for these tests to test anything.
# ---------------------------------------------------------------------------

def test_hide_flag_is_true():
    """Sanity check — tests are only meaningful when the flag is on."""
    assert HIDE_DAMIWORKS_PUBLIC_PRICES is True


# ---------------------------------------------------------------------------
# 1. Pre-intake FAQ: "сколько стоит?"
# ---------------------------------------------------------------------------

class TestPreIntakeFaqPrice:
    def test_no_price_amounts(self):
        answer = pre_intake_faq_answer("price")
        assert not _has_price(answer), f"Found price in pre-intake FAQ: {answer!r}"

    def test_mentions_factors_not_numbers(self):
        answer = pre_intake_faq_answer("price")
        assert any(w in answer.lower() for w in ["каналов", "объём", "интеграц", "автоматиз"])


# ---------------------------------------------------------------------------
# 2. Post-intake: explicit price question
# ---------------------------------------------------------------------------

class TestPriceQuestionAnswer:
    def test_sales_assistant_no_price_amounts(self):
        ctx = _make_ctx("Sales Assistant")
        answer = price_question_answer(ctx)
        assert answer is not None
        assert not _has_price(answer), f"Found price in price_question_answer: {answer!r}"

    def test_integrated_no_price_amounts(self):
        ctx = _make_ctx("Integrated AI Employee", shown_price="от 700 000 ₸")
        answer = price_question_answer(ctx)
        assert answer is not None
        assert not _has_price(answer)

    def test_start_no_price_amounts(self):
        ctx = _make_ctx("Start", shown_price="150 000–200 000 ₸")
        answer = price_question_answer(ctx)
        assert answer is not None
        assert not _has_price(answer)

    def test_mentions_package_name(self):
        ctx = _make_ctx("Sales Assistant")
        answer = price_question_answer(ctx)
        assert "Sales Assistant" in (answer or "")


# ---------------------------------------------------------------------------
# 3. Post-intake: price objection ("это дорого")
# ---------------------------------------------------------------------------

class TestPriceObjectionAnswer:
    def test_no_price_amounts(self):
        ctx = _make_ctx("Sales Assistant")
        answer = price_objection_answer(ctx)
        assert answer is not None
        assert not _has_price(answer), f"Found price in price_objection_answer: {answer!r}"

    def test_mentions_start_as_cheaper(self):
        ctx = _make_ctx("Sales Assistant")
        answer = price_objection_answer(ctx)
        assert "Pilot / Start" in (answer or "")


# ---------------------------------------------------------------------------
# 4. Post-intake: cheaper option ("можно дешевле?")
# ---------------------------------------------------------------------------

class TestCheaperAnswer:
    def test_no_price_amounts(self):
        ctx = _make_ctx()
        answer = cheaper_answer(ctx)
        assert not _has_price(answer), f"Found price in cheaper_answer: {answer!r}"

    def test_mentions_start_label(self):
        ctx = _make_ctx()
        answer = cheaper_answer(ctx)
        assert "Pilot / Start" in answer


# ---------------------------------------------------------------------------
# 5. Post-intake: business details volunteered
# ---------------------------------------------------------------------------

class TestBusinessDetailsAnswer:
    def test_no_price_amounts(self):
        ctx = _make_ctx()
        answer = business_details_answer(ctx)
        assert not _has_price(answer), f"Found price in business_details_answer: {answer!r}"

    def test_includes_contact_ask(self):
        ctx = _make_ctx()
        answer = business_details_answer(ctx)
        assert any(
            kw in answer.lower()
            for kw in ["оставьте", "контакт", "номер", "whatsapp", "telegram"]
        )


# ---------------------------------------------------------------------------
# 6. Output sanitizer guardrail: strips surviving price amounts from LLM output
# ---------------------------------------------------------------------------

class TestSanitizeGuardrail:
    def _sanitize(self, answer: str, user_message: str = "сколько стоит?") -> str:
        from app.api import _sanitize_damiworks_web_answer

        return _sanitize_damiworks_web_answer(
            answer=answer,
            user_message=user_message,
            close_intent=False,
            last_assistant_message="",
        )

    def test_strips_exact_price_amounts(self):
        llm_answer = (
            "Sales Assistant стоит от 350 000 ₸ за запуск и 120 000 ₸ в месяц.\n\n"
            "Расскажите о вашей задаче."
        )
        result = self._sanitize(llm_answer)
        assert not _has_price(result), f"Price survived sanitizer: {result!r}"

    def test_non_price_answer_has_no_prices(self):
        # Use a non-price user message so Step 2 doesn't fire.
        llm_answer = (
            "Sales Assistant подходит для бизнеса с квалификацией лидов.\n\n"
            "Стоимость определяется после разбора задачи. Расскажите о вашей задаче."
        )
        result = self._sanitize(llm_answer, user_message="расскажите подробнее")
        assert not _has_price(result), f"Price in non-price answer: {result!r}"
        assert result  # not empty
