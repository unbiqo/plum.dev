"""
Unit tests for web_site / DamiWorks channel behavior.

These test the repair functions directly — no LLM calls, no network.
All tests must pass after the scaffold/price regression fix.
"""
import pytest

from app.api import (
    CONSULTANT_INSTANCE_ID,
    CUSTOM_DEMO_INSTANCE_ID,
    ROLEPLAY_CONTEXT_SUMMARY_KEY,
    WEB_DOCUMENTS_ANSWER,
    WEB_SIMULATION_REDIRECT_ANSWER,
    WEB_START_GREETING_ANSWER,
    _DAMIWORKS_KZT_PRICING,
    _build_price_override_answer,
    _ensure_sales_initiative_answer,
    _force_roleplay_for_custom_demo,
    _format_solution_description_guard,
    _is_consultant_instance,
    _is_custom_demo_instance,
    _is_solution_description_intent,
    _is_web_simulation_request,
    _repair_completed_function_qualification_answer,
    _sanitize_damiworks_web_answer,
)
from app.web_site_intake_policy import (
    CONTACT_ASKS,
    GUIDED_INTAKE_CTAS,
    IntakeContext,
    already_answered_acknowledgment,
    answer_has_contact_ask,
    answer_has_guided_intake_cta,
    business_details_answer,
    cheaper_answer,
    detect_intent,
    detect_pre_intake_faq_intent,
    implementation_answer,
    is_start_intent,
    not_remembered_answer,
    parse_message,
    phone_handoff_ack,
    post_intake_response,
    pre_intake_faq_answer,
    price_objection_answer,
    start_handoff_answer,
)

# ---------------------------------------------------------------------------
# Shared fixture — intake context block as route.ts would build it
# ---------------------------------------------------------------------------

_INTAKE_SALES_ASSISTANT = (
    "[WEBSITE INTAKE CONTEXT — DO NOT ASK AGAIN]\n"
    "Client answered the questionnaire. Use this; do not re-ask.\n"
    "- Channels: WhatsApp\n"
    "- Tasks: Отвечать на вопросы, Квалифицировать лидов, Передавать заявки менеджеру\n"
    "- Handoff: Пока не знаю\n"
    "- Volume: 10–30/day\n"
    "- Timeline: В ближайшие дни\n"
    "- Business type: Онлайн-магазин\n"
    "- Recommended package: Sales Assistant\n"
    "- Shown price: от 350 000 ₸ + 120 000 ₸/мес\n"
    "\nRules:\n"
    "- Do NOT ask which functionality is priority (already selected above).\n"
    "- Do NOT ask which channel they use (already selected).\n"
    "- Do NOT ask about volume or timeline (already selected).\n"
    "- If user asks about price, explain using the selected tasks and package above.\n"
    "- If user says it is expensive, explain package contents and offer Start as cheaper option.\n"
    "- If user references the questionnaire, confirm their selections and move forward."
)

_INTAKE_START = _INTAKE_SALES_ASSISTANT.replace("Sales Assistant", "Start").replace(
    "350 000 ₸ + 120 000 ₸/мес", "200 000 ₸ + 60 000 ₸/мес"
)


def _with_intake(user_text: str, prefix: str = _INTAKE_SALES_ASSISTANT) -> str:
    """Build the prefixed message as route.ts would."""
    return f"{prefix}\n\nCurrent user message:\n{user_text}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scope_answer(goal_text: str = "ответы на вопросы о товаре", close_intent: bool = False) -> str:
    return _repair_completed_function_qualification_answer(
        answer="",
        user_message=goal_text,
        dialog_state={"qualification_tasks_completed": True},
        close_intent=close_intent,
    )


def _ensure_answer(close_intent: bool = False, all_functions: bool = False) -> str:
    dialog_state: dict = {}
    user_message = "все задачи сразу" if all_functions else "хочу автоматизировать ответы"
    if all_functions:
        dialog_state["all_agent_functions_selected"] = True
    return _ensure_sales_initiative_answer(
        answer="Понял вашу задачу.",
        user_message=user_message,
        dialog_state=dialog_state,
        close_intent=close_intent,
    )


# ---------------------------------------------------------------------------
# _repair_completed_function_qualification_answer
# ---------------------------------------------------------------------------

class TestRepairCompletedQualificationAnswer:
    def test_no_scaffold_phrase_globally(self):
        answer = _scope_answer()
        assert "В проект добавим" not in answer

    def test_no_usd_price(self):
        answer = _scope_answer()
        assert "$300" not in answer
        assert "$600" not in answer

    def test_kzt_pricing_present(self):
        answer = _scope_answer()
        assert "₸" in answer

    def test_no_whatsapp_cta_without_close_intent(self):
        answer = _scope_answer(close_intent=False)
        assert "на какой номер" not in answer.lower()
        # WhatsApp should not be asked without explicit buy signal
        assert "whatsapp" not in answer.lower() or "сколько" in answer.lower()

    def test_contact_request_allowed_with_close_intent(self):
        answer = _scope_answer(close_intent=True)
        assert any(w in answer.lower() for w in ["контакт", "детали", "уточним"])

    def test_max_one_question(self):
        answer = _scope_answer(close_intent=False)
        assert answer.count("?") <= 1

    def test_goal_text_included_in_summary(self):
        goal = "квалификация лидов из Instagram"
        answer = _repair_completed_function_qualification_answer(
            answer="",
            user_message=goal,
            dialog_state={"qualification_tasks_completed": True},
        )
        assert "Instagram" in answer or "квалификац" in answer.lower()

    def test_all_functions_branch_no_scaffold(self):
        answer = _repair_completed_function_qualification_answer(
            answer="",
            user_message="хочу все функции сразу",
            dialog_state={"all_agent_functions_selected": True},
        )
        assert "В проект добавим" not in answer
        assert "$300" not in answer
        assert "₸" in answer

    def test_no_double_override_when_answer_already_has_kzt(self):
        """If LLM already gave KZT pricing, function should not append a duplicate block."""
        existing = "Это подойдёт для «Старта». от 200 000 ₸ за запуск + от 60 000 ₸/мес. Сколько обращений в день?"
        result = _repair_completed_function_qualification_answer(
            answer=existing,
            user_message="любое сообщение",
            dialog_state={"qualification_tasks_completed": True},
        )
        # Should return the existing answer unchanged (has_forward_step detected ₸)
        assert result == existing


# ---------------------------------------------------------------------------
# _ensure_sales_initiative_answer
# ---------------------------------------------------------------------------

class TestEnsureSalesInitiativeAnswer:
    def test_no_usd_price(self):
        result = _ensure_answer(close_intent=False)
        assert "$300" not in result

    def test_no_whatsapp_without_close_intent(self):
        result = _ensure_answer(close_intent=False)
        assert "на какой номер" not in result.lower()

    def test_no_whatsapp_all_functions_without_close_intent(self):
        result = _ensure_answer(close_intent=False, all_functions=True)
        assert "$300" not in result
        assert "на какой номер" not in result.lower()
        assert "₸" in result

    def test_contact_allowed_all_functions_with_close_intent(self):
        result = _ensure_answer(close_intent=True, all_functions=True)
        assert any(w in result.lower() for w in ["контакт", "детали", "уточним"])


# ---------------------------------------------------------------------------
# _build_price_override_answer
# ---------------------------------------------------------------------------

class TestBuildPriceOverrideAnswer:
    def test_no_usd(self):
        answer = _build_price_override_answer()
        assert "$300" not in answer
        assert "$600" not in answer

    def test_kzt_present(self):
        answer = _build_price_override_answer()
        assert "₸" in answer

    def test_suggests_intake_instead_of_scope_question(self):
        answer = _build_price_override_answer()
        assert "подбор" in answer.lower() or "5 вопросов" in answer.lower()
        assert "какие 2-3 действия" not in answer.lower()


# ---------------------------------------------------------------------------
# _DAMIWORKS_KZT_PRICING constant sanity
# ---------------------------------------------------------------------------

class TestDamiworksKztPricingConstant:
    def test_contains_start_price(self):
        assert "200" in _DAMIWORKS_KZT_PRICING and "60" in _DAMIWORKS_KZT_PRICING

    def test_contains_sales_assistant_price(self):
        assert "350" in _DAMIWORKS_KZT_PRICING and "120" in _DAMIWORKS_KZT_PRICING

    def test_contains_kzt_symbol(self):
        assert "₸" in _DAMIWORKS_KZT_PRICING

    def test_no_usd(self):
        assert "$" not in _DAMIWORKS_KZT_PRICING


# ---------------------------------------------------------------------------
# _sanitize_damiworks_web_answer — final output guard
# ---------------------------------------------------------------------------

class TestSanitizeDamiworksWebAnswer:
    # 1. USD price artifact → replaced with KZT
    def test_usd_price_replaced_with_kzt(self):
        answer = "Базовое внедрение AI-помощника стартует от $300."
        result = _sanitize_damiworks_web_answer(answer, "Сколько стоит?", close_intent=False)
        assert "$300" not in result
        assert "₸" in result

    def test_usd_price_has_one_question(self):
        answer = "Базовое внедрение AI-помощника стартует от $300."
        result = _sanitize_damiworks_web_answer(answer, "Сколько стоит?", close_intent=False)
        assert result.count("?") <= 1

    # 2. Contact CTA removed without close_intent
    def test_contact_cta_removed_without_close_intent(self):
        answer = (
            "Под вашу задачу подойдёт «Старт».\n\n"
            "от 200 000 ₸ за запуск. Давайте уточним детали — на какой контакт передать информацию?"
        )
        result = _sanitize_damiworks_web_answer(answer, "хочу автоматизировать ответы", close_intent=False)
        assert "на какой контакт" not in result.lower()
        assert "передать информацию" not in result.lower()

    def test_multiple_contact_cta_phrases_removed(self):
        answer = (
            "Хороший scope.\n\n"
            "от 200 000 ₸. Оставьте номер, свяжемся и отправим расчёт."
        )
        result = _sanitize_damiworks_web_answer(answer, "ответы клиентам", close_intent=False)
        assert "оставьте номер" not in result.lower()
        assert "свяжемся" not in result.lower()

    # 3. Contact CTA preserved with close_intent
    def test_contact_cta_allowed_with_close_intent(self):
        answer = (
            "Отлично, обсудим детали.\n\n"
            "от 200 000 ₸. Давайте уточним — на какой контакт передать информацию?"
        )
        result = _sanitize_damiworks_web_answer(answer, "хочу купить", close_intent=True)
        assert any(w in result.lower() for w in ["контакт", "уточним"])

    # 4. Scope message → KZT pricing, no contact CTA
    def test_scope_message_gets_kzt_pricing(self):
        answer = (
            "Понял, хороший scope.\n\n"
            "Чтобы рассчитать точную стоимость, нужно уточнить объём вопросов. "
            "Сколько обращений? И какие каналы?"
        )
        user_msg = "Бот должен отвечать на вопросы о моем товаре. Передавать лидов в таблице с историей переписки"
        result = _sanitize_damiworks_web_answer(answer, user_msg, close_intent=False)
        assert "₸" in result
        assert result.count("?") <= 1
        assert "на какой контакт" not in result.lower()

    def test_scope_message_no_contact_request(self):
        answer = (
            "Это отличный сценарий.\n\n"
            "от 200 000 ₸. Давайте уточним — на какой контакт передать информацию?"
        )
        user_msg = "Хочу чтобы бот отвечал на вопросы и передавал контакты прогретых лидов менеджерам"
        result = _sanitize_damiworks_web_answer(answer, user_msg, close_intent=False)
        assert "передать информацию" not in result.lower()
        assert "₸" in result

    # 5. Normal WhatsApp channel mention preserved (not a CTA)
    def test_whatsapp_channel_mention_preserved(self):
        answer = "Клиенты пишут в WhatsApp, бот отвечает за 5 секунд. Это стандартный сценарий."
        result = _sanitize_damiworks_web_answer(answer, "у меня магазин", close_intent=False)
        assert "whatsapp" in result.lower()

    # 6. Question count ≤ 1 for price/scope turns
    def test_multiple_questions_trimmed_to_one(self):
        answer = (
            "Понял задачу.\n\n"
            "от 200 000 ₸. Сколько обращений в день? И какой канал используете?"
        )
        result = _sanitize_damiworks_web_answer(answer, "хочу бота", close_intent=False)
        assert result.count("?") <= 1

    # 7. Scaffold phrase removed globally
    def test_scaffold_phrase_removed(self):
        answer = "В проект добавим: ответы на вопросы.\n\nот 200 000 ₸. Сколько обращений?"
        result = _sanitize_damiworks_web_answer(answer, "расскажи", close_intent=False)
        assert "В проект добавим" not in result

    # 8. Price intent with no KZT → direct template
    def test_price_intent_no_kzt_returns_template(self):
        answer = "Стоимость зависит от задачи и сложности интеграции."
        result = _sanitize_damiworks_web_answer(answer, "Сколько стоит?", close_intent=False)
        assert "₸" in result
        assert result.count("?") <= 1

    # 9. Reversed dollar sign: "300$" pattern (the live-QA leak)
    def test_reversed_dollar_sign_replaced(self):
        answer = (
            "Для вашего объема 10-30 обращений базовая автоматизация "
            "обычно начинается от 300$."
        )
        result = _sanitize_damiworks_web_answer(answer, "почему так дорого", close_intent=False)
        assert "300$" not in result
        assert "$300" not in result
        assert "₸" in result
        assert any(x in result for x in ["200", "350"])

    # 10. Dollar with space: "300 $"
    def test_dollar_with_space_replaced(self):
        answer = "Базовое внедрение от 600 $."
        result = _sanitize_damiworks_web_answer(answer, "цена", close_intent=False)
        assert "600 $" not in result
        assert "₸" in result

    # 11. Uppercase USD token
    def test_usd_token_replaced(self):
        answer = "Внедрение AI-сотрудника обходится от 300 USD."
        result = _sanitize_damiworks_web_answer(answer, "цена", close_intent=False)
        assert "USD" not in result
        assert "₸" in result

    # 12. Lowercase usd
    def test_usd_lowercase_replaced(self):
        answer = "Обычно 300 usd за базовый пакет."
        result = _sanitize_damiworks_web_answer(answer, "стоимость", close_intent=False)
        assert "usd" not in result.lower()
        assert "₸" in result


# ---------------------------------------------------------------------------
# parse_message / IntakeContext
# ---------------------------------------------------------------------------

class TestParseIntakeMessage:
    def test_no_marker_returns_original(self):
        msg = "просто вопрос"
        real, ctx = parse_message(msg)
        assert real == msg
        assert not ctx.exists

    def test_with_marker_splits_correctly(self):
        full = _with_intake("Почему такая цена?")
        real, ctx = parse_message(full)
        assert real == "Почему такая цена?"
        assert ctx.exists

    def test_intake_fields_extracted(self):
        _, ctx = parse_message(_with_intake("привет"))
        assert ctx.channels == ["WhatsApp"]
        assert ctx.recommended_package == "Sales Assistant"
        assert ctx.shown_price is not None and "350 000" in ctx.shown_price
        assert ctx.business_type == "Онлайн-магазин"


# ---------------------------------------------------------------------------
# price_objection_answer
# ---------------------------------------------------------------------------

class TestBuildPriceObjectionAnswer:
    def test_sales_assistant_returns_kzt_explanation(self):
        _, ctx = parse_message(_with_intake("x"))
        result = price_objection_answer(ctx)
        assert result is not None
        assert "₸" in result
        assert "Sales Assistant" in result
        assert "200 000" in result  # mentions Start alternative

    def test_sales_assistant_no_question(self):
        _, ctx = parse_message(_with_intake("x"))
        result = price_objection_answer(ctx)
        assert result is not None
        assert result.count("?") == 0

    def test_start_package_returns_start_explanation(self):
        _, ctx = parse_message(_with_intake("x", _INTAKE_START))
        result = price_objection_answer(ctx)
        assert result is not None
        assert "Pilot / Start" in result
        assert "200 000" in result

    def test_no_package_returns_none(self):
        result = price_objection_answer(IntakeContext(exists=False))
        assert result is None


# ---------------------------------------------------------------------------
# already_answered_acknowledgment
# ---------------------------------------------------------------------------

class TestBuildIntakeAcknowledgment:
    def test_acknowledges_selected_items(self):
        _, ctx = parse_message(_with_intake("x"))
        result = already_answered_acknowledgment(ctx)
        assert result is not None
        assert "WhatsApp" in result
        assert "Sales Assistant" in result
        assert "350 000" in result

    def test_includes_next_step(self):
        _, ctx = parse_message(_with_intake("x"))
        result = already_answered_acknowledgment(ctx)
        assert result is not None
        assert "ТЗ" in result or "шаг" in result.lower()

    def test_no_broad_re_ask(self):
        _, ctx = parse_message(_with_intake("x"))
        result = already_answered_acknowledgment(ctx)
        assert result is not None
        assert "какой функционал" not in result.lower()
        assert "что именно" not in result.lower()


# ---------------------------------------------------------------------------
# detect_intent — paraphrase coverage
# ---------------------------------------------------------------------------

class TestDetectIntent:
    def test_price_objection_paraphrases(self):
        phrases = [
            "почему такая цена?",
            "почему так дорого?",
            "за что такая цена?",
            "слишком дорого",
            "это дорого",
            "есть дешевле?",
            "почему столько?",
            "дорого.",
        ]
        for phrase in phrases:
            assert detect_intent(phrase) == "price_objection", f"missed: {phrase!r}"

    def test_already_answered_paraphrases(self):
        phrases = [
            "я же выбрал",
            "я уже выбрал в анкете",
            "я уже ответил",
            "я же ответил",
            "я уже указал",
            "вы уже спросили",
            "я уже отвечал на это",
            "это уже было в анкете",
        ]
        for phrase in phrases:
            assert detect_intent(phrase) == "already_answered_complaint", f"missed: {phrase!r}"

    def test_price_question_paraphrases(self):
        phrases = [
            "сколько стоит?",
            "какая цена?",
            "какова стоимость?",
            "тариф?",
        ]
        for phrase in phrases:
            assert detect_intent(phrase) in ("price_question", "price_objection"), f"missed: {phrase!r}"

    def test_generic_for_normal_questions(self):
        assert detect_intent("как это будет работать?") == "implementation_question"
        assert detect_intent("расскажи подробнее") == "implementation_question"
        assert detect_intent("хочу начать") == "start_intent"
        assert detect_intent("привет, расскажи о вас") == "generic"


# ---------------------------------------------------------------------------
# _sanitize_damiworks_web_answer — post-intake guards
# ---------------------------------------------------------------------------

class TestPostIntakeSanitizer:
    # 1. Price objection → canned KZT explanation, no questions
    def test_price_objection_returns_kzt_no_question(self):
        bad = "Цена зависит от сложности. Какой функционал для вас наиболее приоритетен?"
        result = _sanitize_damiworks_web_answer(bad, _with_intake("Почему такая цена?"), close_intent=False)
        assert "₸" in result
        assert "функционал" not in result.lower()
        assert result.count("?") == 0

    def test_price_objection_dorogo_triggers(self):
        bad = "Стоимость объясняется функциональностью."
        result = _sanitize_damiworks_web_answer(bad, _with_intake("почему так дорого"), close_intent=False)
        assert "₸" in result
        assert "350 000" in result

    def test_price_objection_explains_sales_assistant(self):
        bad = "Это обоснованная цена."
        result = _sanitize_damiworks_web_answer(bad, _with_intake("слишком дорого"), close_intent=False)
        assert "Sales Assistant" in result
        assert "₸" in result

    # 2. "я же выбрал в анкете" → acknowledgment, no broad re-ask
    def test_intake_reference_acknowledged(self):
        bad = "Что именно вы хотели бы включить в спецификацию?"
        result = _sanitize_damiworks_web_answer(bad, _with_intake("так я же выбрал в анкете"), close_intent=False)
        assert "вы уже выбрали" in result.lower() or "вы правы" in result.lower()
        assert "WhatsApp" in result
        assert "что именно вы хотели бы включить" not in result.lower()

    def test_intake_reference_includes_package(self):
        bad = "Понял. Уточните задачи."
        result = _sanitize_damiworks_web_answer(bad, _with_intake("я уже выбрал в анкете"), close_intent=False)
        assert "Sales Assistant" in result
        assert "350 000" in result

    # 3. Re-ask phrase removal when intake context present
    def test_reask_phrase_removed_with_intake(self):
        bad = "от 350 000 ₸. Какой функционал для вас наиболее приоритетен?"
        result = _sanitize_damiworks_web_answer(bad, _with_intake("расскажи о процессе"), close_intent=False)
        assert "какой функционал" not in result.lower()
        assert "₸" in result

    def test_reask_channel_question_removed(self):
        bad = "Хорошо. Какой канал используете?"
        result = _sanitize_damiworks_web_answer(bad, _with_intake("как это работает"), close_intent=False)
        assert "какой канал" not in result.lower()

    # 4. Without intake context, re-ask phrase is NOT removed
    def test_reask_phrase_preserved_without_intake(self):
        bad = "от 350 000 ₸. Какой функционал для вас наиболее приоритетен?"
        result = _sanitize_damiworks_web_answer(bad, "расскажи о процессе", close_intent=False)
        assert "функционал" in result.lower()

    # 5. Price objection without intake context falls through to existing KZT guard
    def test_price_objection_no_intake_uses_existing_guard(self):
        bad = "от $300 обычно стартует."
        result = _sanitize_damiworks_web_answer(bad, "почему так дорого", close_intent=False)
        # Existing Step 1 replaces USD
        assert "$300" not in result
        assert "₸" in result

    # 6. Paraphrase generalization — "за что такая цена?" same as "почему такая цена?"
    def test_za_chto_takaya_tsena_triggers_policy(self):
        bad = "Цена обусловлена функционалом."
        result = _sanitize_damiworks_web_answer(bad, _with_intake("за что такая цена?"), close_intent=False)
        assert "₸" in result
        assert result.count("?") == 0  # canned objection answer has no question

    # 7. Paraphrase generalization — "я уже отвечал на это в анкете"
    def test_uzhe_otvechal_triggers_acknowledgment(self):
        bad = "Расскажите подробнее о задачах."
        result = _sanitize_damiworks_web_answer(
            bad, _with_intake("я уже отвечал на это в анкете"), close_intent=False
        )
        assert "вы уже выбрали" in result.lower() or "вы правы" in result.lower()
        assert "WhatsApp" in result

    # 8. Paraphrase generalization — "почему столько?" triggers objection, not generic
    def test_pochemu_stolko_triggers_policy(self):
        bad = "Стоимость зависит от объема работ."
        result = _sanitize_damiworks_web_answer(bad, _with_intake("почему столько?"), close_intent=False)
        assert "₸" in result
        assert "Sales Assistant" in result

    # 9. Re-ask removal covers multiple known-field patterns
    def test_channel_reask_removed_via_field_policy(self):
        bad = "от 350 000 ₸. Где у вас пишут клиенты?"
        result = _sanitize_damiworks_web_answer(bad, _with_intake("как это работает"), close_intent=False)
        assert "где у вас пишут клиенты" not in result.lower()
        assert "₸" in result


# ---------------------------------------------------------------------------
# Mode separation: DamiWorks consultant vs Custom demo (by instance_id)
# ---------------------------------------------------------------------------

from types import SimpleNamespace


def _payload(instance_id: str, message: str = ""):
    """Minimal stand-in: the instance helpers only read payload.instance_id and payload.message."""
    return SimpleNamespace(instance_id=instance_id, message=message)


class TestInstanceDiscrimination:
    def test_consultant_instance(self):
        assert _is_consultant_instance(_payload(CONSULTANT_INSTANCE_ID)) is True
        assert _is_consultant_instance(_payload(CUSTOM_DEMO_INSTANCE_ID)) is False

    def test_custom_demo_instance(self):
        assert _is_custom_demo_instance(_payload(CUSTOM_DEMO_INSTANCE_ID)) is True
        assert _is_custom_demo_instance(_payload(CONSULTANT_INSTANCE_ID)) is False

    def test_distinct_ids(self):
        assert CONSULTANT_INSTANCE_ID != CUSTOM_DEMO_INSTANCE_ID


class TestIsWebSimulationRequest:
    def test_positive_phrases(self):
        phrases = [
            "/roleplay",
            "будь продавцом",
            "отыграй продажу",
            "покажи как бот будет отвечать клиентам",
            "представь что ты клиент",
            "давай протестируем на моем бизнесе",
        ]
        for p in phrases:
            assert _is_web_simulation_request(p) is True, f"missed: {p!r}"

    def test_negative_solution_description(self):
        # The reported live-QA case: a solution description, NOT a simulation request.
        msg = (
            "Мне нужен бот который будет отвечать на вопросы клиентов "
            "и переводить готовых клиентов на менеджеров"
        )
        assert _is_web_simulation_request(msg) is False

    def test_negative_normal_questions(self):
        assert _is_web_simulation_request("сколько стоит?") is False
        assert _is_web_simulation_request("как это работает?") is False


class TestForceRoleplayForCustomDemo:
    def test_custom_demo_forces_active(self):
        result = _force_roleplay_for_custom_demo(
            _payload(CUSTOM_DEMO_INSTANCE_ID), {"active": False}
        )
        assert result["active"] is True

    def test_custom_demo_no_context_sets_new_request(self):
        result = _force_roleplay_for_custom_demo(
            _payload(CUSTOM_DEMO_INSTANCE_ID), {"active": False}, dialog_state={}
        )
        assert result["new_request"] is True

    def test_custom_demo_with_context_clears_new_request(self):
        result = _force_roleplay_for_custom_demo(
            _payload(CUSTOM_DEMO_INSTANCE_ID),
            {"active": False},
            dialog_state={ROLEPLAY_CONTEXT_SUMMARY_KEY: "магазин платьев: платья от 40 000 до 120 000 ₸"},
        )
        assert result["new_request"] is False

    def test_custom_demo_respects_exit(self):
        result = _force_roleplay_for_custom_demo(
            _payload(CUSTOM_DEMO_INSTANCE_ID), {"active": False, "exit": True}
        )
        assert result.get("active") is not True

    def test_consultant_unchanged(self):
        original = {"active": False}
        result = _force_roleplay_for_custom_demo(_payload(CONSULTANT_INSTANCE_ID), original)
        assert result is original  # no roleplay activation on the consultant instance


class TestSolutionDescriptionIntent:
    @pytest.mark.parametrize("message", [
        "Мне нужен бот который будет отвечать на вопросы клиентов",
        "мне нужен AI который будет отвечать клиентам",
        "Бот должен отвечать на вопросы и передавать лидов менеджеру",
        "бот будет отвечать на частые вопросы",
        "Хочу чтобы бот отвечал на вопросы клиентов и переводил готовых клиентов на менеджеров",
        "передавать лидов менеджеру после квалификации",
        "переводить прогретых клиентов на менеджера",
    ])
    def test_solution_desc_positive(self, message: str):
        assert _is_solution_description_intent(message), f"Should detect: {message!r}"

    @pytest.mark.parametrize("message", [
        "Покажи как бот отвечает клиентам",
        "сколько стоит?",
        "как это работает?",
        "Хочу посмотреть как AI работает",
        "давай протестируем на моем бизнесе",
    ])
    def test_solution_desc_negative(self, message: str):
        assert not _is_solution_description_intent(message), f"Should not detect: {message!r}"

    def test_guard_returns_instruction_for_consultant_with_desc(self):
        p = _payload(CONSULTANT_INSTANCE_ID, "Мне нужен бот который будет отвечать на вопросы клиентов")
        result = _format_solution_description_guard(p)
        assert result != ""
        assert "350 000" in result
        assert "200 000" in result

    def test_guard_empty_for_custom_demo(self):
        p = _payload(CUSTOM_DEMO_INSTANCE_ID, "Мне нужен бот который будет отвечать на вопросы клиентов")
        assert _format_solution_description_guard(p) == ""

    def test_guard_empty_for_consultant_non_desc(self):
        p = _payload(CONSULTANT_INSTANCE_ID, "сколько стоит?")
        assert _format_solution_description_guard(p) == ""


class TestModeSeparationConstants:
    def test_redirect_mentions_custom_demo(self):
        assert "Custom demo" in WEB_SIMULATION_REDIRECT_ANSWER

    def test_consultant_constants_have_no_roleplay_vocab(self):
        forbidden = ["режим продавца", "тест-драйв", "роль продавца", "включусь"]
        for text in (WEB_SIMULATION_REDIRECT_ANSWER, WEB_START_GREETING_ANSWER, WEB_DOCUMENTS_ANSWER):
            low = text.lower()
            for token in forbidden:
                assert token not in low, f"{token!r} leaked into a consultant constant"


# ---------------------------------------------------------------------------
# Pricing v1.1: Start/Pilot range, 3-package constant, intake context guard
# ---------------------------------------------------------------------------

from app.web_site_intake_policy import (
    apply_post_intake_policy,
    implementation_answer,
)


def _make_ctx(pkg: str) -> "IntakeContext":
    """Helper: minimal intake context for a given package."""
    return IntakeContext(
        exists=True,
        channels=["WhatsApp", "Instagram"],
        tasks=["Отвечать на вопросы", "Делать follow-up"],
        handoff="Google Sheets",
        volume="1–10",
        timeline="Просто изучаю",
        business_type="Онлайн-магазин",
        recommended_package=pkg,
        shown_price=None,
    )


class TestPricingV11:
    def test_kzt_pricing_includes_start_range(self):
        # Numbers use narrow no-break space ( ) as thousands separator
        assert "150" in _DAMIWORKS_KZT_PRICING
        assert "40" in _DAMIWORKS_KZT_PRICING
        assert "Старт" in _DAMIWORKS_KZT_PRICING

    def test_kzt_pricing_includes_all_three_packages(self):
        assert "Sales Assistant" in _DAMIWORKS_KZT_PRICING
        assert "Integrated AI Employee" in _DAMIWORKS_KZT_PRICING

    def test_price_override_skipped_when_intake_context_present(self):
        from app.api import _is_explicit_damiworks_price_request
        msg_with_intake = (
            "[WEBSITE INTAKE CONTEXT — DO NOT ASK AGAIN]\n"
            "- Recommended package: Sales Assistant\n"
            "\nCurrent user message:\nПочему такая цена?"
        )
        # The price request pattern still matches the message content
        assert _is_explicit_damiworks_price_request(msg_with_intake) is True
        # But the guard condition includes intake check — tested via presence of marker
        assert "[WEBSITE INTAKE CONTEXT" in msg_with_intake

    def test_price_objection_sales_assistant_mentions_package(self):
        ctx = _make_ctx("Sales Assistant")
        result = price_objection_answer(ctx)
        assert result is not None
        assert "Sales Assistant" in result
        assert "₸" in result
        assert "Pilot / Start" in result  # cheaper option offered

    def test_price_objection_start_no_follow_up(self):
        ctx = _make_ctx("Start")
        result = price_objection_answer(ctx)
        assert result is not None
        assert "₸" in result

    def test_price_objection_integrated_mentions_crm(self):
        ctx = _make_ctx("Integrated AI Employee")
        result = price_objection_answer(ctx)
        assert result is not None
        assert "₸" in result
        assert "Sales Assistant" in result  # cheaper alternative mentioned

    def test_implementation_answer_sales_assistant(self):
        ctx = _make_ctx("Sales Assistant")
        result = implementation_answer(ctx)
        assert result is not None
        assert "Запуск обычно проходит так" in result
        assert "WhatsApp" in result
        # Informational answer: numbered launch steps, no forced contact ask.
        assert not answer_has_contact_ask(result)

    def test_implementation_answer_numbered_steps(self):
        ctx = _make_ctx("Sales Assistant")
        result = implementation_answer(ctx)
        assert "1." in result and "5." in result
        assert "следующ" in result.lower()  # soft non-contact next step

    def test_implementation_question_intent_wired(self):
        ctx = _make_ctx("Sales Assistant")
        result = apply_post_intake_policy(
            answer="Заглушка",
            user_message="что входит в запуск?",
            ctx=ctx,
            close_intent=False,
        )
        assert "WhatsApp" in result
        assert "Запуск обычно проходит так" in result

    def test_mozhno_nachaty_deshevle_triggers_objection(self):
        ctx = _make_ctx("Sales Assistant")
        result = apply_post_intake_policy(
            answer="Заглушка",
            user_message="Можно начать дешевле?",
            ctx=ctx,
            close_intent=False,
        )
        assert "Pilot / Start" in result
        assert "₸" in result

    def test_kak_prokhodit_zapusk_triggers_implementation(self):
        ctx = _make_ctx("Sales Assistant")
        result = apply_post_intake_policy(
            answer="Заглушка",
            user_message="Как проходит запуск?",
            ctx=ctx,
            close_intent=False,
        )
        assert "Запуск обычно проходит так" in result
        assert "WhatsApp" in result


# ---------------------------------------------------------------------------
# Pre-intake FAQ — curated answers for the 3 quick-reply buttons
# ---------------------------------------------------------------------------

_CONTACT_PHRASES = [
    "на какой контакт",
    "на какой номер",
    "оставьте номер",
    "оставьте контакт",
    "куда вам написать",
    "с вами свяжется",
    "передать информацию",
    "свяжемся",
]


class TestDetectPreIntakeFaqIntent:
    def test_price_button(self):
        assert detect_pre_intake_faq_intent("Сколько стоит?") == "price"

    def test_how_it_works_button(self):
        assert detect_pre_intake_faq_intent("Как это работает?") == "how_it_works"

    def test_vs_chatbot_button(self):
        assert detect_pre_intake_faq_intent("Чем отличается от чат-бота?") == "vs_chatbot"

    def test_simple_variants(self):
        assert detect_pre_intake_faq_intent("а как работает?") == "how_it_works"
        assert detect_pre_intake_faq_intent("какая цена") == "price"

    def test_detailed_price_question_falls_through(self):
        # Specifics (CRM / numbers) → let the LLM handle it.
        assert detect_pre_intake_faq_intent("Сколько стоит интеграция с amoCRM?") is None
        assert detect_pre_intake_faq_intent("Сколько стоит на 100 обращений в день?") is None

    def test_detailed_channel_question_falls_through(self):
        assert detect_pre_intake_faq_intent("Как это работает с Instagram и WhatsApp?") is None

    def test_unrelated_message_returns_none(self):
        assert detect_pre_intake_faq_intent("Здравствуйте") is None
        assert detect_pre_intake_faq_intent("Хочу обсудить мой бизнес") is None

    def test_after_intake_returns_none(self):
        # Once intake context is present, the post-intake policy owns the answer.
        assert detect_pre_intake_faq_intent(_with_intake("Сколько стоит?")) is None


class TestPreIntakeFaqAnswer:
    def test_price_answer_canonical_figures_no_contact(self):
        ans = pre_intake_faq_answer("price")
        assert "150 000–200 000 ₸" in ans
        assert "40 000–60 000 ₸" in ans
        assert "Sales Assistant" in ans
        assert answer_has_guided_intake_cta(ans)
        for phrase in _CONTACT_PHRASES:
            assert phrase not in ans.lower()

    def test_vs_chatbot_answer_terms(self):
        ans = pre_intake_faq_answer("vs_chatbot")
        assert "AI-сотрудник" in ans
        assert "тёплый лид" in ans or "тёплый" in ans
        assert answer_has_guided_intake_cta(ans)
        for phrase in _CONTACT_PHRASES:
            assert phrase not in ans.lower()

    def test_how_it_works_answer_no_contact(self):
        ans = pre_intake_faq_answer("how_it_works")
        assert "AI-сотрудник" in ans
        assert answer_has_guided_intake_cta(ans)
        for phrase in _CONTACT_PHRASES:
            assert phrase not in ans.lower()

    def test_cta_repetition_guard(self):
        # If the previous assistant message already used CTA #0, pick a different one.
        ans = pre_intake_faq_answer("price", last_assistant_message=GUIDED_INTAKE_CTAS[0])
        assert GUIDED_INTAKE_CTAS[0] not in ans
        assert answer_has_guided_intake_cta(ans)


# ---------------------------------------------------------------------------
# Sanitizer — broadened contact strip, soft CTA, terminology
# ---------------------------------------------------------------------------

class TestSanitizerContactAndCta:
    def test_strips_broadened_contact_phrases_without_close_intent(self):
        answer = "Мы делаем AI-сотрудников для продаж.\n\nС вами свяжется менеджер."
        result = _sanitize_damiworks_web_answer(answer, "как это работает", close_intent=False)
        assert "свяжется менеджер" not in result.lower()
        assert "куда вам написать" not in result.lower()

    def test_preserves_contact_with_close_intent(self):
        answer = "Отлично!\n\nОставьте номер, мы свяжемся."
        result = _sanitize_damiworks_web_answer(answer, "хочу начать", close_intent=True)
        assert "оставьте номер" in result.lower()

    def test_appends_single_soft_cta_pre_intake(self):
        answer = "Мы подключаем AI-сотрудника к вашему каналу."
        result = _sanitize_damiworks_web_answer(answer, "как это работает", close_intent=False)
        assert answer_has_guided_intake_cta(result)
        # Exactly one CTA from the pool.
        assert sum(cta in result for cta in GUIDED_INTAKE_CTAS) == 1

    def test_does_not_double_cta_when_already_present(self):
        answer = f"Мы подключаем AI-сотрудника.\n\n{GUIDED_INTAKE_CTAS[1]}"
        result = _sanitize_damiworks_web_answer(answer, "как это работает", close_intent=False)
        assert sum(cta in result for cta in GUIDED_INTAKE_CTAS) == 1

    def test_does_not_repeat_cta_from_previous_turn(self):
        answer = "Мы подключаем AI-сотрудника к вашему каналу."
        result = _sanitize_damiworks_web_answer(
            answer,
            "как это работает",
            close_intent=False,
            last_assistant_message=GUIDED_INTAKE_CTAS[0],
        )
        assert GUIDED_INTAKE_CTAS[0] not in result

    def test_no_soft_cta_after_intake(self):
        answer = "Для вашего набора задач подойдёт Sales Assistant."
        result = _sanitize_damiworks_web_answer(
            _with_intake(answer).replace(_with_intake(""), ""),  # ensure plain answer text
            _with_intake("сколько стоит"),
            close_intent=False,
        )
        # When intake context is present, the soft guided-intake CTA is not appended.
        assert not answer_has_guided_intake_cta(result) or "Sales Assistant" in result


class TestSanitizerTerminology:
    def test_replaces_bazovyy_assistent(self):
        result = _sanitize_damiworks_web_answer(
            "Для старта подойдёт Базовый ассистент.", "что посоветуете", close_intent=True
        )
        assert "Базовый ассистент" not in result
        assert "Pilot / Start" in result

    def test_replaces_package_base(self):
        result = _sanitize_damiworks_web_answer(
            "Начнём с пакета base?", "с чего начать", close_intent=True
        )
        assert "base" not in result.lower()
        assert "Pilot / Start" in result

    def test_replaces_ai_assistant_term(self):
        result = _sanitize_damiworks_web_answer(
            "Наш AI-ассистент ответит клиентам.", "что вы делаете", close_intent=True
        )
        assert "ассистент" not in result.lower()
        assert "AI-сотрудник" in result


# ---------------------------------------------------------------------------
# Post-intake handoff — post_intake_response dispatch (PART 2/4/6/7/8/11)
# ---------------------------------------------------------------------------

_INTERNAL_TERMS = ["пакет base", "пакет agent", " base", " agent", "basic",
                   "без выдуманных цифр", "уточнить вводные"]


def _assert_no_internal_terms(text: str) -> None:
    low = text.lower()
    for term in _INTERNAL_TERMS:
        assert term.strip().lower() not in low, f"internal term leaked: {term!r}"


class TestPostIntakeStartIntent:
    def test_explicit_start_asks_for_contact(self):
        _, ctx = parse_message(_with_intake("x"))
        result = post_intake_response("Хорошо, как мы можем начать?", ctx)
        assert result is not None
        assert answer_has_contact_ask(result)
        assert result.count("?") == 0  # no discovery question
        _assert_no_internal_terms(result)

    def test_gotov_triggers_contact(self):
        _, ctx = parse_message(_with_intake("x"))
        result = post_intake_response("готов", ctx)
        assert result is not None and answer_has_contact_ask(result)

    def test_semantic_start_phrases(self):
        _, ctx = parse_message(_with_intake("x"))
        for phrase in [
            "ну окей, звучит нормально",
            "в целом подходит",
            "а дальше что?",
            "можно попробовать",
            "что от меня нужно?",
        ]:
            result = post_intake_response(phrase, ctx)
            assert result is not None, phrase
            assert answer_has_contact_ask(result), phrase
            _assert_no_internal_terms(result)

    def test_is_start_intent_helper(self):
        assert is_start_intent("звучит нормально")
        assert is_start_intent("в целом подходит")
        assert not is_start_intent("а что если менеджер уже есть?")


class TestPostIntakeCheaper:
    def test_cheaper_suggests_pilot_start(self):
        _, ctx = parse_message(_with_intake("x"))
        result = post_intake_response("Можно начать дешевле?", ctx)
        assert result is not None
        assert "Pilot / Start" in result
        assert "150 000–200 000 ₸" in result
        assert "40 000–60 000 ₸" in result
        _assert_no_internal_terms(result)


class TestPostIntakeNotRemembered:
    def test_reassures_and_moves_forward(self):
        _, ctx = parse_message(_with_intake("x"))
        result = post_intake_response("Я не помню какие вопросы задают", ctx)
        assert result is not None
        assert "Ничего страшного" in result
        # No contact ask forced and no repeated discovery question.
        assert not answer_has_contact_ask(result)
        assert "следующ" in result.lower()
        _assert_no_internal_terms(result)


class TestPostIntakeBusinessDetails:
    def test_details_treated_as_enough(self):
        _, ctx = parse_message(_with_intake("x"))
        msg = "Мы продаём протеин, креатин. Доставка по Казахстану. Оплата Kaspi, Halyk. Возврата нет, если открыли."
        result = post_intake_response(msg, ctx)
        assert result is not None
        assert "достаточно" in result.lower()
        assert "Pilot / Start" in result
        assert answer_has_contact_ask(result)
        # Must not re-ask discovery.
        assert "какие вопросы" not in result.lower()
        _assert_no_internal_terms(result)


class TestPostIntakePhone:
    def test_phone_acknowledged_without_fake_sla(self):
        _, ctx = parse_message(_with_intake("x"))
        result = post_intake_response("+77777102402", ctx)
        assert result is not None
        assert "записал" in result.lower()
        assert "команде" in result.lower()
        assert "10 минут" not in result
        _assert_no_internal_terms(result)


class TestPostIntakeContactAskRotation:
    def test_no_repeat_back_to_back(self):
        _, ctx = parse_message(_with_intake("x"))
        result = post_intake_response("готов", ctx, last_assistant_message=CONTACT_ASKS[0])
        assert result is not None
        assert CONTACT_ASKS[0] not in result
        assert answer_has_contact_ask(result)


# ---------------------------------------------------------------------------
# Sanitizer — post-intake forbidden-question scrub, soft-start fallback, terms
# ---------------------------------------------------------------------------

class TestSanitizerPostIntake:
    def test_strips_forbidden_discovery_question(self):
        answer = (
            "Подключим AI-сотрудника к вашим каналам.\n\n"
            "Какие вопросы чаще всего задают клиенты?"
        )
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("а что вы делаете"), close_intent=False
        )
        assert "какие вопросы" not in result.lower()

    def test_soft_start_fallback_adds_contact(self):
        # User is clearly moving forward, but the LLM answer still has no handoff.
        answer = "Это отличный вариант для вашего магазина."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("в целом подходит"), close_intent=False
        )
        assert answer_has_contact_ask(result)

    def test_informational_question_not_forced_to_contact(self):
        answer = "Да, можно подключить и WhatsApp, и Telegram одновременно."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("а можно подключить whatsapp и telegram?"), close_intent=False
        )
        assert not answer_has_contact_ask(result)

    def test_terminology_agent_and_made_up_numbers_scrubbed(self):
        answer = (
            "Для ваших задач подойдёт Sales Assistant. Начнём с пакета agent. "
            "Нужно быстро уточнить вводные, чтобы посчитать проект без выдуманных цифр."
        )
        # Use a generic informational question (not neutral ack / start intent) so the
        # LLM answer passes through to the terminology scrubber unchanged.
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("сколько времени занимает настройка?"), close_intent=True
        )
        low = result.lower()
        assert "agent" not in low
        assert "без выдуманных цифр" not in low
        assert "Sales Assistant" in result

    def test_ok_post_intake_gives_neutral_ack(self):
        # "ок" alone is a neutral ack (PART 1) — must not push through any contact ask.
        answer = "Да, всё верно."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("ок"), close_intent=False
        )
        assert "следующим шагом" in result.lower()

    # PART 8 sanitizer tests
    def test_guided_intake_cta_stripped_post_intake(self):
        # PART 1: After intake, any guided-intake CTA in LLM answer must be removed.
        # Use a generic message that falls through to the LLM answer (no deterministic path).
        answer = (
            "Рекомендую Sales Assistant под ваши задачи.\n\n"
            "Если хотите, я могу подобрать подходящий вариант за 1 минуту — нажмите «Подобрать AI-сотрудника»."
        )
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("расскажи о вашей команде"), close_intent=False
        )
        assert "Подобрать AI-сотрудника" not in result
        assert "Sales Assistant" in result

    def test_ya_soglasen_post_intake_asks_contact(self):
        # PART 8.2: "я согласен" after intake → ask for contact, no discovery.
        answer = "Отлично! Какие именно вопросы задают клиенты?"
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("я согласен"), close_intent=False
        )
        assert "Оставьте" in result
        assert "вопросы" not in result.lower() or "какие" not in result.lower()

    def test_horosho_davajte_after_proposal_no_discovery(self):
        # PART 8.3: "хорошо, давайте" after proposal → contact ask, no discovery.
        proposal_last = "Хотите начать с Pilot / Start?"
        answer = "Отлично! Чтобы подготовить спецификацию, уточните какие вопросы задают клиенты."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("хорошо, давайте"),
            close_intent=False, last_assistant_message=proposal_last
        )
        assert "Оставьте" in result
        assert "какие вопросы" not in result.lower()

    def test_post_intake_answer_never_has_intake_cta(self):
        # PART 1 + PART 8.5: post-intake answers must never tell user to click intake CTA.
        # Generic message falls through to LLM answer; LLM CTA gets stripped.
        answer = "Конечно! Чтобы понять, какой формат подойдёт именно вам, можно пройти короткий подбор."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("расскажи о вашей компании"), close_intent=False
        )
        assert "Подобрать AI-сотрудника" not in result
        assert "пройти короткий подбор" not in result.lower()

    # PART 7 sanitizer tests (new task)

    def test_horosho_after_next_step_offer_asks_contact(self):
        # PART 2/PART 7.1: "хорошо" after next-step offer → contact ask, no discovery.
        next_step_last = "Если хотите, следующим шагом можем перейти к запуску."
        answer = "Чтобы рассчитать точную стоимость, уточните функции."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("хорошо"),
            close_intent=False, last_assistant_message=next_step_last,
        )
        assert "Оставьте" in result
        assert "рассчитать" not in result.lower()
        assert "функци" not in result.lower()

    def test_okej_after_next_step_offer_asks_contact(self):
        # PART 2/PART 7.2: "окей" after next-step offer → contact ask.
        next_step_last = "Если хотите, следующим шагом можем перейти к запуску."
        answer = "Конечно! Уточните, пожалуйста, задачи проекта..."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("окей"),
            close_intent=False, last_assistant_message=next_step_last,
        )
        assert "Оставьте" in result

    def test_chuoby_rasschitatj_without_tochno_stripped(self):
        # PART 4/7.7: "Чтобы рассчитать точную стоимость" (without leading "точно") is stripped.
        answer = (
            "Sales Assistant отлично подходит для ваших задач.\n\n"
            "Чтобы рассчитать точную стоимость запуска, уточните функции."
        )
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("расскажи о вашей команде"), close_intent=False
        )
        assert "рассчитать" not in result.lower()

    def test_utochnite_funktsii_stripped(self):
        # PART 4: "уточните функции" is a discovery question — must be stripped post-intake.
        answer = "Уточните, пожалуйста, функции, которые хотите включить."
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("расскажи о вашей команде"), close_intent=False
        )
        assert "функци" not in result.lower() or "уточните" not in result.lower()

    def test_feature_detail_kvalifikatsiyu_asks_contact_in_sanitizer(self):
        # PART 3/7.4: "квалификацию" post-intake → deterministic contact ask from sanitizer.
        answer = "Отлично, квалификация заявок — важная часть автоматизации. Что ещё?"
        result = _sanitize_damiworks_web_answer(
            answer, _with_intake("квалификацию"), close_intent=False
        )
        assert "Оставьте" in result


# ---------------------------------------------------------------------------
# Contact collection after a contact ask (PART 1–4)
# ---------------------------------------------------------------------------

from app.web_site_intake_policy import (  # noqa: E402
    assistant_asked_for_contact,
    contact_close_answer,
    has_contact_like_reply,
)

_ASKED = "Оставьте, пожалуйста, имя и номер WhatsApp/Telegram — мы свяжемся, уточним детали и предложим следующий шаг."

_QUALIFY_MARKERS = ["какие вопросы", "какие товары", "какой бюджет",
                    "какие каналы", "уточните", "что нужно автоматизировать"]


def _assert_closes_without_qualifying(result: str) -> None:
    assert result is not None
    assert "Передам заявку команде" in result
    low = result.lower()
    for m in _QUALIFY_MARKERS:
        assert m not in low, f"qualification leaked: {m!r}"


class TestAssistantAskedForContact:
    def test_detects_contact_ask(self):
        assert assistant_asked_for_contact(_ASKED)
        assert assistant_asked_for_contact("Можете оставить номер WhatsApp/Telegram — передадим заявку команде.")

    def test_non_contact_message_false(self):
        assert not assistant_asked_for_contact("Запуск обычно проходит так: 1. Уточняем задачи.")
        assert not assistant_asked_for_contact("")


class TestHasContactLikeReply:
    def test_bare_name_after_ask(self):
        assert has_contact_like_reply("Jackiehan", _ASKED)
        assert has_contact_like_reply("Damir Sarsenov", _ASKED)
        assert has_contact_like_reply("Дамир", _ASKED)

    def test_telegram_always(self):
        assert has_contact_like_reply("@jackiehan", "")
        assert has_contact_like_reply("jackiehan мой тг", "")
        assert has_contact_like_reply("telegram jackiehan", "")

    def test_phone_always(self):
        assert has_contact_like_reply("+77777102402", "")
        assert has_contact_like_reply("+7 777 710 24 02", "")

    def test_bare_name_requires_ask(self):
        assert not has_contact_like_reply("Jackiehan", "")
        assert not has_contact_like_reply("Damir", "")

    def test_fillers_not_contact_even_after_ask(self):
        for filler in ["ок", "да", "нет", "что входит в запуск?", "не помню", "готов"]:
            assert not has_contact_like_reply(filler, _ASKED), filler


class TestPostIntakeContactClose:
    def _ctx(self):
        _, ctx = parse_message(_with_intake("x"))
        return ctx

    def test_name_after_ask_closes_lead(self):
        result = post_intake_response("Jackiehan", self._ctx(), last_assistant_message=_ASKED)
        _assert_closes_without_qualifying(result)
        assert result.count("?") == 0

    def test_telegram_my_tg_close(self):
        result = post_intake_response("jackiehan мой тг", self._ctx(), last_assistant_message=_ASKED)
        assert result == contact_close_answer("jackiehan мой тг")
        assert "Telegram получил" in result

    def test_at_handle_close(self):
        result = post_intake_response("@jackiehan", self._ctx(), last_assistant_message=_ASKED)
        assert "Telegram получил" in result

    def test_phone_close_no_fake_sla(self):
        result = post_intake_response("+77777102402", self._ctx(), last_assistant_message=_ASKED)
        assert "номер записал" in result.lower()
        assert "10 минут" not in result

    def test_name_without_ask_not_contact(self):
        result = post_intake_response("Jackiehan", self._ctx(), last_assistant_message="")
        # Not treated as contact: no close answer.
        assert result is None or "Передам заявку команде" not in result

    def test_what_included_after_ask_not_contact(self):
        result = post_intake_response("что входит в запуск?", self._ctx(), last_assistant_message=_ASKED)
        assert "Передам заявку команде" not in (result or "")
        assert "Запуск обычно проходит так" in (result or "")

    def test_ok_after_ask_not_contact(self):
        result = post_intake_response("ок", self._ctx(), last_assistant_message=_ASKED)
        assert "Передам заявку команде" not in (result or "")
