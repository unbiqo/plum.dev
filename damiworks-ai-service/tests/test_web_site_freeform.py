"""Tests for the DamiWorks consultant pre-intake free-form layer.

Covers the dental-clinic transcript regression: free-form profile extraction,
loop-breaking ("я же сказал", "это не важно"), contact-offer intent
("контакт будешь брать?"), the scoping-call close once context is sufficient,
CTA once-per-conversation behavior, and Discovery-mode price safety.

No LLM calls — policy functions and the sanitizer are tested directly.
"""
from __future__ import annotations

import re

from app.api import (
    _WEB_GUIDED_INTAKE_CTA_RE,
    _sanitize_damiworks_web_answer,
)
from app.web_site_intake_policy import (
    FreeformProfile,
    contact_offer_answer,
    extract_freeform_profile,
    freeform_close_answer,
    has_enough_freeform_context,
    is_contact_offer_question,
    pre_intake_faq_answer,
    profile_to_intake_context,
    resolve_preintake_turn,
)

# Exact DamiWorks package price amounts must never appear (Discovery mode).
_PRICE_RE = re.compile(
    r"\b(?:150\s*000|200\s*000|350\s*000|700\s*000|40\s*000|60\s*000|120\s*000)\s*₸"
)

# The dental transcript's user messages, verbatim.
_DENTAL_TEXTS = [
    "здравствуйте, у меня своя стоматологи и мне нужно отвечать на вопросы клиентов "
    "и назначать appointment. вы можете такое сделать?",
    "мне клиенты пишут в ватсап. Трафик приходит с инстаграм, 2гис и сайта.",
    "1с",
]


def _dental_profile() -> FreeformProfile:
    return extract_freeform_profile(_DENTAL_TEXTS)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def test_extraction_from_dental_transcript() -> None:
    p = _dental_profile()
    assert set(p.channels) >= {"WhatsApp", "Instagram", "2GIS", "Website"}
    assert "Отвечать на вопросы" in p.tasks
    assert "Запись клиентов" in p.tasks
    assert p.crm == "1С"
    assert p.business_type == "Стоматология"
    assert has_enough_freeform_context(p)


def test_extraction_empty_for_smalltalk() -> None:
    p = extract_freeform_profile(["привет", "зачем изучать английский?"])
    assert not has_enough_freeform_context(p)


def test_profile_to_intake_context_maps_fields() -> None:
    ctx = profile_to_intake_context(_dental_profile())
    assert ctx.exists
    assert "WhatsApp" in ctx.channels
    assert ctx.handoff == "1С"
    assert ctx.business_type == "Стоматология"
    assert ctx.recommended_package in ("Start", "Sales Assistant")


# ---------------------------------------------------------------------------
# Pre-intake turn resolver
# ---------------------------------------------------------------------------

def test_short_info_drop_with_enough_context_moves_to_close() -> None:
    # After the dental context, "срм" must not trigger another module question.
    turn = resolve_preintake_turn("срм", _dental_profile(), "Какой именно модуль 1С вы используете?",
                                  calendly_enabled=True)
    assert turn.answer is not None
    assert turn.lead_status == "contact_requested"
    low = turn.answer.casefold()
    assert "достаточно для первичного разбора" in low
    assert "звонк" in low  # booking is offered
    assert "какие именно функции" not in low
    assert not _PRICE_RE.search(turn.answer)
    assert "подобрать ai-сотрудника" not in low


def test_already_said_breaks_the_loop() -> None:
    turn = resolve_preintake_turn("я же сказал уже", _dental_profile(),
                                  "Какие именно функции должен выполнять AI-сотрудник?",
                                  calendly_enabled=True)
    assert turn.answer is not None
    assert "достаточно для первичного разбора" in turn.answer.casefold()
    assert "функци" not in turn.answer.casefold()


def test_dismissal_does_not_reask() -> None:
    turn = resolve_preintake_turn("это не важно", _dental_profile(), "", calendly_enabled=False)
    assert turn.answer is not None
    assert "whatsapp/telegram" in turn.answer.casefold()
    assert "функци" not in turn.answer.casefold()


def test_close_not_repeated_twice_in_a_row() -> None:
    prev = freeform_close_answer(_dental_profile(), calendly_enabled=True)
    turn = resolve_preintake_turn("хорошо", _dental_profile(), prev, calendly_enabled=True)
    assert turn.answer is None  # falls through to the LLM instead of re-closing


def test_contact_offer_question_is_damiworks_conversion_intent() -> None:
    for msg in (
        "контакт будешь брать?",
        "куда номер оставить?",
        "как с вами связаться?",
        "как заявку оставить?",
    ):
        assert is_contact_offer_question(msg), msg
        turn = resolve_preintake_turn(msg, _dental_profile(), "", calendly_enabled=True)
        assert turn.answer is not None, msg
        assert turn.lead_status == "contact_requested"
        low = turn.answer.casefold()
        # Calendly-primary, user's own contact secondary — never about end customers.
        assert "звонка" in low or "звонк" in low
        assert "whatsapp/telegram" in low
        assert "клиент" not in low


def test_contact_offer_answer_without_calendly_asks_for_contact() -> None:
    ans = contact_offer_answer(calendly_enabled=False)
    assert "ваше имя" in ans.casefold()
    assert "звонка" not in ans.casefold()


def test_phone_message_collects_contact_pre_intake() -> None:
    turn = resolve_preintake_turn("Хорошо, вот мой номер +7 777 282 88 22",
                                  _dental_profile(), "", calendly_enabled=True)
    assert turn.lead_status == "contact_collected"
    assert turn.contact is not None and turn.contact.kind == "phone"
    assert turn.answer is not None


def test_channel_mention_of_telegram_is_not_treated_as_contact() -> None:
    profile = extract_freeform_profile(["клиенты пишут в телеграм и ватсап"])
    turn = resolve_preintake_turn("клиенты пишут в телеграм и ватсап", profile, "")
    assert turn.lead_status != "contact_collected"


def test_price_question_left_to_faq_layer() -> None:
    # "сколько стоит?" is handled by the curated FAQ, not the free-form close.
    turn = resolve_preintake_turn("сколько будет стоить?", _dental_profile(), "")
    assert turn.answer is None
    # And the FAQ price body stays Discovery-safe.
    faq = pre_intake_faq_answer("price", suppress_cta=True)
    assert not _PRICE_RE.search(faq)
    assert "₸" not in faq


def test_close_answer_uses_safe_integration_wording() -> None:
    ans = freeform_close_answer(_dental_profile(), calendly_enabled=True)
    low = ans.casefold()
    assert "1с" in low
    assert "напрямую, через api или таблицу" in low
    assert "настроим автоматическую" not in low
    assert not _PRICE_RE.search(ans)


# ---------------------------------------------------------------------------
# Sanitizer: CTA once per conversation, discovery-question strip, overpromise
# ---------------------------------------------------------------------------

def test_cta_not_appended_when_already_offered_in_history() -> None:
    out = _sanitize_damiworks_web_answer(
        answer="Да, такой сценарий подходит.",
        user_message="а вы поддерживаете 2гис?",
        close_intent=False,
        intake_cta_already_offered=True,
    )
    assert not _WEB_GUIDED_INTAKE_CTA_RE.search(out)


def test_cta_still_offered_once_when_never_offered() -> None:
    out = _sanitize_damiworks_web_answer(
        answer="Да, такой сценарий подходит.",
        user_message="а вы поддерживаете 2гис?",
        close_intent=False,
        intake_cta_already_offered=False,
    )
    assert _WEB_GUIDED_INTAKE_CTA_RE.search(out)


def test_faq_answer_suppresses_cta_when_flagged() -> None:
    ans = pre_intake_faq_answer("how_it_works", suppress_cta=True)
    assert not _WEB_GUIDED_INTAKE_CTA_RE.search(ans)


def test_sanitizer_strips_forced_function_question_with_enough_context() -> None:
    profile = _dental_profile()
    fallback = freeform_close_answer(profile, calendly_enabled=True)
    out = _sanitize_damiworks_web_answer(
        answer="Чтобы перейти к расчету, уточните, какие именно функции должен выполнять AI-сотрудник в первую очередь?",
        user_message="это не важно",
        close_intent=False,
        intake_cta_already_offered=True,
        freeform_enough_context=True,
        freeform_close_fallback=fallback,
    )
    assert "какие именно функции" not in out.casefold()
    assert "достаточно для первичного разбора" in out.casefold()


def test_sanitizer_softens_integration_overpromise() -> None:
    out = _sanitize_damiworks_web_answer(
        answer="Понял, вы используете 1С. Мы настроим автоматическую передачу заявок прямо в вашу 1С.",
        user_message="1с",
        close_intent=False,
        intake_cta_already_offered=True,
    )
    low = out.casefold()
    assert "настроим автоматическую передачу" not in low
    assert "обсудим отдельно" in low


def test_freeform_answers_never_reintroduce_damiworks_prices() -> None:
    for text in (
        freeform_close_answer(_dental_profile(), calendly_enabled=True),
        freeform_close_answer(FreeformProfile(), calendly_enabled=False),
        contact_offer_answer(calendly_enabled=True),
        contact_offer_answer(calendly_enabled=False),
    ):
        assert not _PRICE_RE.search(text)
        assert "₸" not in text
