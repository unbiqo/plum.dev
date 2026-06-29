"""Unit tests for the DamiWorks lead-stage model and owner-notification format.

Pure functions — no LLM, no network, no DB.
"""
from app.lead_notifier import format_lead_created, format_lead_updated
from app.web_site_intake_policy import (
    _is_neutral_ack,
    is_start_intent,
    neutral_ack_answer,
    parse_message,
)
from app.web_site_lead import (
    LeadStage,
    assistant_proposed_next_step,
    is_affirmation,
    resolve_post_intake_turn,
)

_INTAKE = (
    "[WEBSITE INTAKE CONTEXT — DO NOT ASK AGAIN]\n"
    "- Channels: WhatsApp\n"
    "- Tasks: Отвечать на вопросы, Квалифицировать лидов\n"
    "- Handoff: Google Sheets\n"
    "- Volume: 10–30/day\n"
    "- Timeline: В ближайшие дни\n"
    "- Business type: Услуги\n"
    "- Recommended package: Sales Assistant\n"
    "- Shown price: от 350 000 ₸ + 120 000 ₸/мес\n"
)
_PROPOSAL = (
    "Да, можно начать с Pilot / Start. Это проще и дешевле.\n\nХотите начать с Pilot / Start?"
)
_CONTACT_ASK = "Отлично. Оставьте, пожалуйста, имя и номер WhatsApp/Telegram."


def _ctx(user_text: str):
    real, ctx = parse_message(f"{_INTAKE}\n\nCurrent user message:\n{user_text}")
    return real, ctx


def _resolve(user_text: str, last_assistant: str, lead_closed: bool = False):
    real, ctx = _ctx(user_text)
    return resolve_post_intake_turn(real, ctx, last_assistant, lead_closed=lead_closed)


_NO_QUALIFY = ["какие вопросы", "какие товары", "какие каналы", "какой бюджет",
               "что именно вы хотите автоматизировать", "куда передавать"]


def _assert_no_qualify(text: str) -> None:
    low = text.lower()
    for m in _NO_QUALIFY:
        assert m not in low, f"qualification leaked: {m!r}"


class TestAffirmation:
    def test_basic_affirmations(self):
        for w in ["да", "хорошо", "подходит", "давайте", "ок", "конечно", "поехали"]:
            assert is_affirmation(w), w

    def test_negatives_and_long(self):
        assert not is_affirmation("нет")
        assert not is_affirmation("а что входит в запуск")
        assert not is_affirmation("да но я ещё думаю над этим вариантом")

    def test_proposal_detection(self):
        assert assistant_proposed_next_step(_PROPOSAL)
        assert assistant_proposed_next_step(_CONTACT_ASK)
        assert not assistant_proposed_next_step("Запуск проходит так: уточняем задачи.")


class TestPackageAcceptance:
    def test_cheaper_then_da_asks_contact(self):
        # PART 9.1 — cheaper proposes Pilot / Start, no contact yet.
        cheaper = _resolve("Можно начать дешевле?", _CONTACT_ASK)
        assert cheaper.stage == LeadStage.package_discussion
        assert "Хотите начать с Pilot / Start?" in cheaper.answer
        assert "Оставьте" not in cheaper.answer

        # PART 9.2 — bare and compound affirmatives after a proposal ask for contact.
        for w in ["да", "хорошо", "подходит", "давайте", "да, давайте", "ок, давайте"]:
            turn = _resolve(w, _PROPOSAL)
            assert turn.stage == LeadStage.contact_requested, w
            assert "Оставьте" in turn.answer
            _assert_no_qualify(turn.answer)

    def test_da_with_proposal_is_contact_request(self):
        # PART 2: bare "да" post-intake = strong start intent, regardless of whether
        # the assistant explicitly proposed a step (that was only needed before PART 2).
        turn = _resolve("да", "Запуск проходит так: уточняем задачи и каналы.")
        assert turn.stage == LeadStage.contact_requested

    def test_compound_affirmative_without_proposal_not_blindly_closed(self):
        # PART 5 test 6: compound affirmatives without a proposal must NOT force contact.
        # The affirmation branch only fires when the assistant actually proposed a step.
        neutral = "Запуск проходит в несколько шагов. Первый — уточняем задачи."
        for w in ["да, давайте", "ок, давайте"]:
            turn = _resolve(w, neutral)
            assert turn.stage != LeadStage.contact_requested, w
            assert turn.answer is None or "Оставьте" not in (turn.answer or ""), w


class TestContactCollection:
    def test_name_closes(self):
        turn = _resolve("Jackiehan", _CONTACT_ASK)
        assert turn.stage == LeadStage.contact_collected
        assert turn.contact.kind == "name"
        assert "Передам заявку команде" in turn.answer
        _assert_no_qualify(turn.answer)

    def test_telegram_closes(self):
        turn = _resolve("jackiehan мой тг", _CONTACT_ASK)
        assert turn.stage == LeadStage.contact_collected
        assert turn.contact.kind == "telegram"
        assert "Telegram получил" in turn.answer

    def test_phone_closes_no_fake_sla(self):
        turn = _resolve("+77777102402", _CONTACT_ASK)
        assert turn.stage == LeadStage.contact_collected
        assert turn.contact.kind == "phone"
        assert turn.contact.phone == "+77777102402"
        assert "10 минут" not in turn.answer

    def test_closed_lead_does_not_requalify(self):
        # PART 9.6 — after close, another message returns the terminal answer.
        turn = _resolve("а ещё вопрос про товары", _CONTACT_ASK, lead_closed=True)
        assert turn.stage == LeadStage.closed
        assert "уже отправлена" in turn.answer.lower()
        _assert_no_qualify(turn.answer)


_SOFT_NEXT_STEP_MSG = "Хорошо. Если захотите продолжить, следующим шагом можно перейти к запуску."


class TestNeutralAck:
    """PART 7.1–7.2: neutral acks must not trigger a contact ask or discovery."""

    def test_ponyal_is_neutral_ack(self):
        assert _is_neutral_ack("понял")
        assert _is_neutral_ack("понятно")
        assert _is_neutral_ack("ясно")
        assert _is_neutral_ack("ок")

    def test_da_is_not_neutral_ack(self):
        assert not _is_neutral_ack("да")

    def test_neutral_ack_post_intake_gives_soft_answer(self):
        for word in ("понял", "понятно", "ясно"):
            turn = _resolve(word, _PROPOSAL)
            # The proposal IS there — but neutral ack is NOT an affirmation so the
            # affirmation+proposal path in resolve_post_intake_turn must not fire.
            assert turn.stage != LeadStage.contact_requested, word
            assert "Оставьте" not in turn.answer, word
            _assert_no_qualify(turn.answer)

    def test_neutral_ack_without_proposal_gives_soft_continuation(self):
        neutral = "Запуск проходит в несколько шагов. Первый — уточняем задачи."
        for word in ("понял", "понятно", "ясно"):
            turn = _resolve(word, neutral)
            assert "следующим шагом" in turn.answer.lower(), word
            assert "Оставьте" not in turn.answer, word

    def test_da_after_soft_next_step_asks_contact(self):
        # PART 7: after neutral_ack_answer which contains "следующим шагом можно перейти к
        # запуску", user says "да" → proposal detected → contact_requested.
        turn = _resolve("да", _SOFT_NEXT_STEP_MSG)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer
        _assert_no_qualify(turn.answer)


class TestStrongStartIntent:
    """PART 7.4–7.5 and PART 2: strong start phrases directly ask for contact."""

    def test_horosho_davajte_start(self):
        neutral_last = "Запуск проходит так: уточняем задачи и каналы."
        turn = _resolve("хорошо, давайте старт", neutral_last)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer
        _assert_no_qualify(turn.answer)

    def test_davajte_start(self):
        turn = _resolve("давайте старт", "Вот как выглядит запуск.")
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_nachynaem(self):
        turn = _resolve("начинаем", "Вот как выглядит запуск.")
        assert turn.stage == LeadStage.contact_requested

    def test_chto_ot_menya_nuzhno(self):
        turn = _resolve("что от меня нужно?", "Вот как выглядит запуск.")
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_da_alone_is_start_intent(self):
        # PART 2: bare "да" post-intake = strong start intent.
        assert is_start_intent("да")
        turn = _resolve("да", "Вот как выглядит запуск (без явного предложения).")
        assert turn.stage == LeadStage.contact_requested

    def test_ok_without_proposal_is_neutral(self):
        # "ок" without a proposal must NOT ask for contact.
        neutral_last = "Запуск проходит так: уточняем задачи и каналы."
        turn = _resolve("ок", neutral_last)
        assert turn.stage != LeadStage.contact_requested
        assert "Оставьте" not in turn.answer

    # PART 8 — new test cases from the bug report
    def test_ya_soglasen_is_start_intent(self):
        assert is_start_intent("я согласен")
        turn = _resolve("я согласен", "Вот как выглядит запуск.")
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_soglasen_is_start_intent(self):
        assert is_start_intent("согласен")
        turn = _resolve("согласен", "Рекомендую Sales Assistant.")
        assert turn.stage == LeadStage.contact_requested

    def test_typo_s_oglasen_is_start_intent(self):
        # "с огласен" — accidental space in "согласен"
        assert is_start_intent("я с огласен")
        turn = _resolve("я с огласен", "Рекомендую Sales Assistant.")
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_compound_neutral_plus_agreement_asks_contact(self):
        # "понятно. я с огласен" — neutral ack followed by agreement with typo.
        # is_start_intent finds "согласен" anywhere via .search().
        assert is_start_intent("понятно. я с огласен")
        turn = _resolve("понятно. я с огласен", "Рекомендую Sales Assistant.")
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer
        _assert_no_qualify(turn.answer)

    def test_horosho_davajte_after_proposal_asks_contact(self):
        # PART 3: "хорошо, давайте" after proposal → contact_requested, no discovery.
        turn = _resolve("хорошо, давайте", _PROPOSAL)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer
        _assert_no_qualify(turn.answer)

    def test_kak_nachaty_is_start_intent(self):
        # "как начать" moved from implementation to strong start intent per PART 2.
        assert is_start_intent("как начать")
        turn = _resolve("как начать", "Рекомендую Sales Assistant.")
        assert turn.stage == LeadStage.contact_requested


_NEXT_STEP_SOFT = "Если хотите, следующим шагом можем перейти к запуску."
_NEXT_STEP_SOFT2 = "Если захотите продолжить, я подскажу следующий шаг."


class TestNextStepAcceptance:
    """PART 2: affirmation after a next-step offer → contact ask, no discovery."""

    def test_horosho_after_next_step_asks_contact(self):
        turn = _resolve("хорошо", _NEXT_STEP_SOFT)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer
        _assert_no_qualify(turn.answer)

    def test_okej_after_next_step_asks_contact(self):
        turn = _resolve("окей", _NEXT_STEP_SOFT)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_ok_after_next_step_asks_contact(self):
        turn = _resolve("ок", _NEXT_STEP_SOFT)
        assert turn.stage == LeadStage.contact_requested

    def test_da_davajte_after_next_step_asks_contact(self):
        turn = _resolve("да, давайте", _NEXT_STEP_SOFT)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_horosho_after_second_soft_step_asks_contact(self):
        # Second SOFT_NEXT_STEPS variant — also triggers via assistant_asked_for_contact
        turn = _resolve("хорошо", _NEXT_STEP_SOFT2)
        assert turn.stage == LeadStage.contact_requested

    def test_mojem_perejti_k_zapusku_pattern(self):
        # New _PROPOSED_NEXT_STEP_RE pattern: "можем перейти к запуску"
        from app.web_site_lead import assistant_proposed_next_step
        assert assistant_proposed_next_step("Если готовы, можем перейти к запуску.")

    def test_esli_hotite_prodolzhit_pattern(self):
        from app.web_site_lead import assistant_proposed_next_step
        assert assistant_proposed_next_step("Если хотите продолжить, дайте знать.")

    def test_neutral_message_no_next_step_pattern(self):
        # A plain informational message without next-step should NOT trigger
        from app.web_site_lead import assistant_proposed_next_step
        assert not assistant_proposed_next_step("Запуск проходит в несколько этапов.")


class TestFeatureDetail:
    """PART 3: concrete feature mention post-intake → acknowledge + contact ask."""

    def test_kvalifikatsiyu_is_feature_detail(self):
        from app.web_site_intake_policy import is_feature_detail
        assert is_feature_detail("квалификацию")

    def test_dostavku_is_feature_detail(self):
        from app.web_site_intake_policy import is_feature_detail
        assert is_feature_detail("доставку")

    def test_sbor_kontaktov_is_feature_detail(self):
        from app.web_site_intake_policy import is_feature_detail
        assert is_feature_detail("сбор контактов")

    def test_follow_up_is_feature_detail(self):
        from app.web_site_intake_policy import is_feature_detail
        assert is_feature_detail("follow-up")

    def test_question_not_feature_detail(self):
        from app.web_site_intake_policy import is_feature_detail
        assert not is_feature_detail("какая доставка?")

    def test_long_sentence_not_feature_detail(self):
        from app.web_site_intake_policy import is_feature_detail
        assert not is_feature_detail("хочу чтобы бот квалифицировал заявки очень подробно и точно")

    def test_kvalifikatsiyu_asks_contact(self):
        turn = _resolve("квалификацию", _PROPOSAL)
        assert turn.stage == LeadStage.contact_requested
        assert "добавим" in turn.answer.lower()
        assert "Оставьте" in turn.answer
        _assert_no_qualify(turn.answer)

    def test_dostavku_after_next_step_asks_contact(self):
        turn = _resolve("доставку", _NEXT_STEP_SOFT)
        assert turn.stage == LeadStage.contact_requested
        assert "Оставьте" in turn.answer

    def test_feature_detail_not_misread_as_name(self):
        # "квалификацию" after a contact ask must NOT be classified as a name contact
        from app.web_site_intake_policy import parse_contact
        p = parse_contact("квалификацию", _CONTACT_ASK)
        assert p.kind is None, "feature detail must not be parsed as a contact name"


class TestNotificationFormat:
    _lead = {
        "interest_level": "hot",
        "package_recommended": "Sales Assistant",
        "business_type": "Онлайн-магазин",
        "channels": ["WhatsApp", "Instagram"],
        "tasks": ["Ответы на вопросы", "Квалификация лидов"],
        "volume": "10–30",
        "timeline": "В ближайшие дни",
        "user_contact_name": "Jackiehan",
        "user_contact_telegram": "@jackiehan",
    }

    def test_created_is_new_lead_waiting(self):
        msg = format_lead_created(self._lead)
        assert "Новый лид" in msg
        assert "ждём контакт" in msg
        assert "пока нет" in msg

    def test_updated_is_distinct_not_new_lead(self):
        msg = format_lead_updated(self._lead)
        assert "Лид обновлён" in msg
        assert "Новый лид" not in msg
        assert "Jackiehan" in msg
        assert "@jackiehan" in msg
        assert "готов к связи" in msg
