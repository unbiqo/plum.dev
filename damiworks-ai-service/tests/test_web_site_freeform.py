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
    assert set(p.channels) >= {"WhatsApp", "Instagram", "2ГИС", "Website"}
    assert "Отвечать на вопросы" in p.tasks
    assert "Запись клиентов" in p.tasks
    assert p.crm == "1С"
    assert p.business_type == "Стоматология"
    assert has_enough_freeform_context(p)


def test_extraction_survives_user_typo_in_business() -> None:
    # «стоматологи» (typo) still maps to the canonical label.
    p = extract_freeform_profile(["у меня своя стоматологи"])
    assert p.business_type == "Стоматология"


# ---------------------------------------------------------------------------
# Negation handling — "нет CRM" / "не используем WhatsApp" must not register
# ---------------------------------------------------------------------------

def test_no_crm_is_not_extracted_as_crm() -> None:
    p = extract_freeform_profile(["У нас нет CRM, всё ведём вручную, но есть 1с? нет, 1с тоже нет"])
    assert p.crm is None

    p2 = extract_freeform_profile(["У нас нет CRM, всё ведём вручную"])
    assert p2.crm is None


def test_negated_channel_is_not_extracted() -> None:
    p = extract_freeform_profile(["Мы не используем WhatsApp"])
    assert "WhatsApp" not in p.channels


def test_negation_keeps_the_positive_alternative() -> None:
    p = extract_freeform_profile(["у нас нет ватсапа, только инстаграм"])
    assert "WhatsApp" not in p.channels
    assert "Instagram" in p.channels


def test_trailing_negation_refers_to_previous_clause() -> None:
    p = extract_freeform_profile(["Instagram раньше был, сейчас не работает"])
    assert "Instagram" not in p.channels


# ---------------------------------------------------------------------------
# Close threshold — one weak signal must not trigger the scoping-call close
# ---------------------------------------------------------------------------

def test_single_channel_without_tasks_is_not_enough_for_close() -> None:
    p = extract_freeform_profile(["у меня бизнес, клиенты пишут в ватсап"])
    assert not has_enough_freeform_context(p)
    turn = resolve_preintake_turn("клиенты пишут в ватсап", p, "", calendly_enabled=True)
    assert turn.answer is None  # the LLM asks its one clarifying question instead


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
    # "хорошо" right after the close is acceptance: move to the contact ask,
    # never repeat the "этого достаточно..." close verbatim.
    prev = freeform_close_answer(_dental_profile(), calendly_enabled=True)
    turn = resolve_preintake_turn("хорошо", _dental_profile(), prev, calendly_enabled=True)
    assert turn.answer is not None
    assert turn.lead_status == "contact_requested"
    assert "достаточно для первичного разбора" not in turn.answer


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


def test_high_frequency_damiworks_templates_avoid_em_dashes() -> None:
    # Production-polish guard: the most frequently shown deterministic
    # DamiWorks templates must not reintroduce AI-sounding em dashes.
    # Deliberately NOT a global ban — Russian copy may use a dash naturally.
    from app.web_site_intake_policy import (
        CALENDLY_CONTACT_ASK,
        CONTACT_ASKS,
        GUIDED_INTAKE_CTAS,
        contact_close_answer,
        phone_handoff_ack,
    )

    samples = [
        CALENDLY_CONTACT_ASK,
        *CONTACT_ASKS,
        *GUIDED_INTAKE_CTAS,
        phone_handoff_ack(),
        contact_close_answer("+7 777 282 88 22"),
        contact_offer_answer(calendly_enabled=True),
        contact_offer_answer(calendly_enabled=False),
        freeform_close_answer(_dental_profile(), calendly_enabled=True),
        freeform_close_answer(_dental_profile(), calendly_enabled=False),
    ]
    for text in samples:
        assert "—" not in text, text


# ---------------------------------------------------------------------------
# Round 8: generalized sales policy across niches
# ---------------------------------------------------------------------------

_SCHOOL_TEXTS = ["У меня онлайн-школа, заявки из Instagram, надо отвечать и записывать на пробный урок."]
_TG_CHANNEL_TEXTS = [
    "Трафик из TikTok в Telegram-бота, бот должен продавать закрытый канал "
    "и сохранять клиентов в Google Sheets."
]


def test_extraction_online_school() -> None:
    p = extract_freeform_profile(_SCHOOL_TEXTS)
    assert "Instagram" in p.channels
    assert "Отвечать на вопросы" in p.tasks and "Запись клиентов" in p.tasks
    assert p.business_type == "Обучение"
    assert has_enough_freeform_context(p)


def test_extraction_paid_telegram_channel() -> None:
    p = extract_freeform_profile(_TG_CHANNEL_TEXTS)
    assert "TikTok" in p.channels and "Telegram" in p.channels
    assert "Продажа доступа" in p.tasks
    assert "Собирать контакты" in p.tasks
    assert p.crm == "Google Sheets"
    assert has_enough_freeform_context(p)


def test_enough_context_close_generalizes_across_niches() -> None:
    # Same close policy for school and paid-channel niches, not only dentistry:
    # a short low-info reply with enough context moves to the call, and an
    # explicit "да" converts directly.
    for texts in (_SCHOOL_TEXTS, _TG_CHANNEL_TEXTS):
        profile = extract_freeform_profile(texts)
        short = resolve_preintake_turn("ага, всё так", profile, "Какой у вас объём заявок?",
                                       calendly_enabled=True)
        assert short.answer is not None, texts
        assert "достаточно для первичного разбора" in short.answer.casefold()
        assert short.lead_status == "contact_requested"

        yes = resolve_preintake_turn("да", profile, "Какой у вас объём заявок?", calendly_enabled=True)
        assert yes.answer is not None and yes.lead_status == "contact_requested"
        assert "звонк" in yes.answer.casefold() or "whatsapp" in yes.answer.casefold()


def test_business_plus_tasks_is_enough_without_channel() -> None:
    # "Салон красоты, хочу чтобы бот отвечал и записывал клиентов." — 2 signals.
    p = extract_freeform_profile(["Салон красоты, хочу чтобы бот отвечал и записывал клиентов"])
    assert has_enough_freeform_context(p)


def test_weak_context_never_closes_early() -> None:
    for msg in ("Нужен бот", "Хочу автоматизацию", "Клиенты пишут"):
        p = extract_freeform_profile([msg])
        assert not has_enough_freeform_context(p), msg
        turn = resolve_preintake_turn(msg, p, "")
        # Falls through to the LLM (one useful question), except explicit
        # conversion intents, which may offer the call.
        if turn.answer is not None:
            assert "достаточно для первичного разбора" not in turn.answer.casefold(), msg


def test_dalshe_chto_after_enough_context_converts() -> None:
    turn = resolve_preintake_turn("дальше что?", _dental_profile(), "", calendly_enabled=True)
    assert turn.answer is not None
    assert turn.lead_status == "contact_requested"
    low = turn.answer.casefold()
    assert "звонк" in low or "whatsapp" in low


def test_kak_nachat_converts() -> None:
    turn = resolve_preintake_turn("как начать?", _dental_profile(), "", calendly_enabled=True)
    assert turn.answer is not None
    assert turn.lead_status == "contact_requested"


def test_ok_after_proposal_converts_not_requalifies() -> None:
    prev = freeform_close_answer(_dental_profile(), calendly_enabled=True)
    for msg in ("ок", "да", "хорошо", "давайте"):
        turn = resolve_preintake_turn(msg, _dental_profile(), prev, calendly_enabled=True)
        assert turn.answer is not None, msg
        assert turn.lead_status == "contact_requested", msg
        assert "?" not in turn.answer or "какой" not in turn.answer.casefold(), msg


def test_gibberish_is_not_treated_as_confirmation() -> None:
    for msg in ("lf", "asdf", "qwe"):
        turn = resolve_preintake_turn(msg, _dental_profile(), "", calendly_enabled=True)
        assert turn.answer is not None, msg
        assert "не совсем понял" in turn.answer.casefold(), msg
        assert turn.lead_status is None, msg  # never a lead-state change
    # Known short words are not gibberish.
    from app.web_site_intake_policy import is_gibberish_message

    for word in ("ok", "crm", "api"):
        assert not is_gibberish_message(word), word


def test_refusals_break_loop() -> None:
    for msg in ("не знаю", "не хочу отвечать", "давай дальше"):
        turn = resolve_preintake_turn(msg, _dental_profile(), "Какой именно модуль 1С?",
                                      calendly_enabled=True)
        assert turn.answer is not None, msg
        assert turn.lead_status == "contact_requested", msg
        assert "модуль" not in turn.answer.casefold(), msg


def test_no_internal_package_names_in_discovery_templates() -> None:
    from app.web_site_intake_policy import (
        IntakeContext,
        already_answered_acknowledgment,
        business_details_answer,
        cheaper_answer,
        price_objection_answer,
        price_question_answer,
    )

    ctx = IntakeContext(
        exists=True, channels=["WhatsApp"], tasks=["Отвечать на вопросы"],
        business_type="Стоматология", recommended_package="Sales Assistant",
    )
    answers = [
        price_objection_answer(ctx),
        price_question_answer(ctx),
        already_answered_acknowledgment(ctx),
        cheaper_answer(ctx),
        business_details_answer(ctx),
        freeform_close_answer(_dental_profile(), calendly_enabled=True),
        contact_offer_answer(calendly_enabled=True),
    ]
    for text in answers:
        assert text is not None
        for label in ("Pilot / Start", "Sales Assistant", "Integrated AI Employee"):
            assert label not in text, (label, text)
        assert not _PRICE_RE.search(text)


def test_sanitizer_replaces_internal_labels_in_llm_answers() -> None:
    out = _sanitize_damiworks_web_answer(
        answer="Вам подойдёт Sales Assistant, а дешевле — Pilot / Start или Integrated AI Employee.",
        user_message="что посоветуете?",
        close_intent=False,
        intake_cta_already_offered=True,
    )
    for label in ("Pilot / Start", "Sales Assistant", "Integrated AI Employee"):
        assert label not in out


def test_sanitizer_softens_absolute_promises() -> None:
    out = _sanitize_damiworks_web_answer(
        answer="Это абсолютно реализуемо, мы точно настроим и автоматически всё сделаем.",
        user_message="а сложно ли это?",
        close_intent=False,
        intake_cta_already_offered=True,
    )
    low = out.casefold()
    assert "абсолютно реализуемо" not in low
    assert "точно настроим" not in low
    assert "автоматически всё сделаем" not in low and "автоматически все сделаем" not in low


def test_sanitizer_softens_automatic_access_granting() -> None:
    out = _sanitize_damiworks_web_answer(
        answer="Бот будет автоматически выдавать доступ в закрытый канал после оплаты.",
        user_message="как выдаётся доступ?",
        close_intent=False,
        intake_cta_already_offered=True,
    )
    low = out.casefold()
    assert "автоматически выдавать доступ" not in low
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
