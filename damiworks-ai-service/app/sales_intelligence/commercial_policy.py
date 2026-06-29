"""Strategy-aware commercial / price policy (Phase 8).

Deterministic. Given the current strategy (conversation_mode, wow, next_best_action),
roi_result, the legacy dialog_state and the detected price/close intent, it produces a
``CommercialPolicy`` describing how a *price* turn should be handled — plus a short
``price_response_guidance`` instruction for the generation path.

It does NOT change the deterministic price override, the checkout/product-card path, or the
legacy stage machine. It only adds mode-aware guidance on the LLM generation path (api.py).
No SaaS pricing numbers are hardcoded here; concrete prices come from tenant config/RAG.
"""
from __future__ import annotations

import re
from typing import Any

_PRICE_PATTERNS = (
    r"скольк[оа]\s+стоит", r"скольк[оа]\s+буд", r"\bцен[аы]\b", r"стоимост", r"\bпрайс\b",
    r"\bпочем\b", r"во\s+скольк", r"бюджет\s+на\s+проект",
)
# Explicit close / buy intent — only these may allow checkout/card behavior (task C).
_CLOSE_PATTERNS = (
    r"хочу\s+купить", r"\bкупить\b", r"оформ", r"давай(?:те)?\s+начн", r"куда\s+(?:оплат|плат)",
    r"как\s+оплат", r"готов\s+(?:купить|оплатит|начать|оформ|стартова)", r"\bберу\b",
    r"погнали", r"стартуем", r"поех(?:а|)ли",
)


def _norm(text: str) -> str:
    return (text or "").casefold().replace("ё", "е")


def detect_price_intent(message: str) -> bool:
    text = _norm(message)
    return any(re.search(p, text) for p in _PRICE_PATTERNS)


def detect_close_intent(message: str) -> bool:
    text = _norm(message)
    return any(re.search(p, text) for p in _CLOSE_PATTERNS)


# --- per-mode commercial framing (short behavioral constraints only) --------

_HEADER = "[КОММЕРЧЕСКАЯ ПОЛИТИКА — приоритет над инструкциями по дожиму] "

_SIMPLE_PRICE = (
    "Цена зависит от сценария (просто отвечать на заявки / квалифицировать клиентов / "
    "интеграция с CRM / расчёт ROI). Дай ориентир по сценариям, если он есть из конфигурации; "
    "иначе честно скажи, что цена зависит от scope. Без анкеты, максимум один мягкий вопрос про "
    "scope. Карточку заказа не показывай."
)
_MICRO_PRICE = (
    "Свяжи цену с экономией времени владельца и тем, что не теряются заявки. Сначала простой "
    "AI-помощник, без энтерпрайз-аудита и тяжёлого ROI. Максимум один простой вопрос: сколько "
    "примерно сообщений/заявок в день приходит. Карточку заказа не показывай."
)
_INTEGRATION_PRICE = (
    "Цена зависит от числа систем и сложности (CRM/склад/оплата/телефония/API) и действий AI. "
    "Сначала scope/спецификация, без выдуманной точной сметы. Максимум один вопрос: какие "
    "системы надо связать в первой версии."
)
_ROI_PRICE_SHOW = (
    "Свяжи цену с ожидаемым месячным эффектом/окупаемостью из уже посчитанного ROI (порядок "
    "эффекта). Безопасно: 'если эти допущения близки к реальности', 'точнее посчитаем после "
    "проверки цифр'. Не гарантируй ROI и не выдумывай числа. Предложи спецификацию или короткий созвон."
)
_ROI_PRICE_NOSHOW = (
    "Не показывай ROI-цифры и не выдумывай их. Объясни, что для оценки эффекта не хватает одного "
    "показателя; спроси его, только если уместно. Цену привяжи к scope, без точной сметы."
)
_LOW_FIT_PRICE = (
    "Не дожимай и не толкай к полному внедрению. Честно скажи, когда платный AI-агент окупается "
    "(когда уже есть поток заявок или повторяющиеся диалоги). Предложи лёгкий следующий шаг или "
    "объяснение. Карточку заказа не показывай."
)
_POST_ROLEPLAY_PRICE = (
    "Свяжи цену с 'таким AI под ваш бизнес' (как только что в демо). Задай один вопрос про scope "
    "или предложи спецификацию/короткий созвон. Не теряй вау-момент демо."
)
_CLOSE_READY = (
    "Клиент готов двигаться дальше. Можно переходить к оформлению/контакту по существующей логике; "
    "коротко подтверди следующий шаг, без лишних вопросов."
)

_NO_PRICE_MODES_FALLBACK = _SIMPLE_PRICE


def _close_state(dialog_state: dict[str, Any] | None) -> bool:
    ds = dialog_state or {}
    return bool(ds.get("close_consented") or ds.get("contact_phone_collected"))


def build_commercial_policy(
    *,
    conversation_mode: str | None,
    wow_mechanism: str | None = None,
    next_best_action_type: str | None = None,
    bot_guidance: dict[str, Any] | None = None,
    roi_result: dict[str, Any] | None = None,
    price_intent: bool = False,
    close_intent: bool = False,
    dialog_state: dict[str, Any] | None = None,
    post_roleplay: bool = False,
    must_give_value_now: bool = False,
    roleplay_active: bool = False,
) -> dict[str, Any]:
    """Build the deterministic commercial policy for this turn."""
    reasons: list[str] = []
    close_state = _close_state(dialog_state)
    roi_can_show = bool(roi_result and roi_result.get("can_show_to_user"))

    if roleplay_active:
        reasons.append("roleplay_active: commercial policy is no-op")
        return _policy(price_intent=False, reasons=reasons, mode=conversation_mode)

    # Checkout/card is advisory here (existing legacy logic still owns the real card). It may be
    # allowed only on explicit close intent or pre-existing close state (task C).
    should_show_checkout_card = close_intent or close_state
    should_avoid_hard_close = not (close_intent or close_state) and conversation_mode in (
        "simple_explainer", "low_fit_nurture", "microbusiness_helper",
    )
    should_use_roi_context = conversation_mode in ("light_roi_diagnostic", "full_roi_audit") and roi_can_show
    should_offer_call = conversation_mode in ("full_roi_audit", "integration_discovery") or close_intent
    should_offer_specification = should_offer_call
    should_show_price_orientation = price_intent and not should_show_checkout_card
    should_ask_scope_question = price_intent and not must_give_value_now and not close_intent
    max_questions = 0 if (must_give_value_now or close_intent) else 1

    # Pick the commercial angle / guidance text.
    if close_intent:
        angle, guidance = "close_ready", _CLOSE_READY
        reasons.append("explicit close intent -> proceed via existing logic")
    elif post_roleplay:
        angle, guidance = "post_roleplay", _POST_ROLEPLAY_PRICE
        reasons.append("post-roleplay price -> connect to demo context")
    elif conversation_mode == "microbusiness_helper":
        angle, guidance = "time_saving", _MICRO_PRICE
    elif conversation_mode == "integration_discovery":
        angle, guidance = "integration_scope", _INTEGRATION_PRICE
    elif conversation_mode in ("light_roi_diagnostic", "full_roi_audit"):
        if roi_can_show:
            angle, guidance = "roi_payback", _ROI_PRICE_SHOW
        else:
            angle, guidance = "roi_metric_gap", _ROI_PRICE_NOSHOW
    elif conversation_mode == "low_fit_nurture":
        angle, guidance = "no_pressure", _LOW_FIT_PRICE
    else:  # simple_explainer / cold / unknown
        angle, guidance = "scenario_orientation", _SIMPLE_PRICE

    if must_give_value_now and price_intent:
        reasons.append("must_give_value_now: give commercial value first, max one soft question")

    guidance_text = (_HEADER + guidance) if (price_intent or post_roleplay) else ""

    return _policy(
        price_intent=price_intent,
        reasons=reasons,
        mode=conversation_mode,
        should_show_price_orientation=should_show_price_orientation,
        should_show_checkout_card=should_show_checkout_card,
        should_offer_call=should_offer_call,
        should_offer_specification=should_offer_specification,
        should_use_roi_context=should_use_roi_context,
        should_avoid_hard_close=should_avoid_hard_close,
        should_ask_scope_question=should_ask_scope_question,
        max_questions=max_questions,
        commercial_angle=angle,
        price_response_guidance=guidance_text,
        close_intent=close_intent,
    )


def _policy(
    *,
    price_intent: bool,
    reasons: list[str],
    mode: str | None,
    should_show_price_orientation: bool = False,
    should_show_checkout_card: bool = False,
    should_offer_call: bool = False,
    should_offer_specification: bool = False,
    should_use_roi_context: bool = False,
    should_avoid_hard_close: bool = False,
    should_ask_scope_question: bool = False,
    max_questions: int = 1,
    commercial_angle: str = "none",
    price_response_guidance: str = "",
    close_intent: bool = False,
) -> dict[str, Any]:
    return {
        "should_answer_price": bool(price_intent),
        "should_show_price_orientation": should_show_price_orientation,
        "should_show_checkout_card": should_show_checkout_card,
        "should_offer_call": should_offer_call,
        "should_offer_specification": should_offer_specification,
        "should_use_roi_context": should_use_roi_context,
        "should_avoid_hard_close": should_avoid_hard_close,
        "should_ask_scope_question": should_ask_scope_question,
        "max_questions": max_questions,
        "commercial_angle": commercial_angle,
        "price_response_guidance": price_response_guidance,
        "price_intent_detected": bool(price_intent),
        "close_intent_detected": bool(close_intent),
        "logging_reasons": reasons,
        "conversation_mode": mode,
    }
