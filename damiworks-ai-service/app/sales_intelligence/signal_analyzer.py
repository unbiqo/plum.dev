"""Heuristic signal analyzer + extraction gate (Phase 1, no LLM).

Phase 1 deliberately does NOT call the LLM extractor. This module derives a cheap,
deterministic slice of business facts and behavior signals from the current message and
recent history, plus a gate that decides whether an LLM extraction *would* be warranted
(used only to log a skip reason in shadow mode).
"""
from __future__ import annotations

import re

from .defaults import new_field_value


def _normalize(text: str) -> str:
    return (text or "").casefold().replace("ё", "е").strip()


# --- keyword groups ---------------------------------------------------------

_LOW_SIGNAL_TOKENS = {
    "ок", "окей", "ok", "k", "да", "нет", "ага", "угу", "понял", "поняла",
    "понятно", "спасибо", "спс", "хорошо", "ясно", "ладно", "допустим", "+",
}

_OWNER_PATTERNS = (
    r"\bя\s+сам\b", r"\bсам\s+отвеча", r"\bсама\s+отвеча", r"\bлично\s+отвеча",
    r"\bвсе\s+пишут\s+мне\b", r"\bя\s+одна?\b",
)

_CRM_KEYWORDS = {
    "amocrm": "amoCRM", "amo": "amoCRM", "амосрм": "amoCRM", "амо": "amoCRM",
    "bitrix": "Bitrix24", "битрикс": "Bitrix24", "crm": "CRM", "црм": "CRM",
    "таблиц": "tables", "excel": "Excel", "гугл-таблиц": "Google Sheets",
}

_CHANNEL_KEYWORDS = {
    "whatsapp": "whatsapp", "ватсап": "whatsapp", "вотсап": "whatsapp",
    "instagram": "instagram", "инстаграм": "instagram", "инст": "instagram",
    "директ": "instagram", "telegram": "telegram", "телеграм": "telegram",
    "сайт": "website", "авито": "avito",
}

_PAIN_KEYWORDS = {
    "не успева": "not_enough_time", "забыва": "forgetting_followups",
    "теря": "losing_leads", "хаос": "chaos_in_chats", "долго отвеча": "slow_response",
    "не отвеча": "slow_response", "не сплю": "owner_overload", "завал": "owner_overload",
}

_INTEGRATION_KEYWORDS = {
    "склад": "warehouse", "наличи": "stock", "календ": "calendar", "оплат": "payment",
    "телефони": "telephony", "api": "api", "1с": "1c", "доставк": "delivery",
}

_PRICE_PATTERNS = (r"скольк[оа]\s+стоит", r"скольк[оа]\s+буд", r"\bцен[аы]\b", r"стоимост", r"\bпрайс\b", r"почем")
_DEMO_PATTERNS = (r"\bдемо\b", r"покажит", r"\broleplay\b", r"тест-?драйв")
_HOW_PATTERNS = (
    r"как\s+это\s+работает", r"что\s+вы.{0,12}делает", r"чем\s+(?:вы\s+)?занимает",
    r"как\s+работает", r"что\s+(?:вы\s+)?умеет",
)
_IRRITATED_PATTERNS = (r"зачем\s+столько\s+вопрос", r"много\s+вопрос", r"к\s+чему\s+вопрос", r"что\s+так\s+много\s+вопрос")
_LOW_FIT_PATTERNS = (
    r"нет\s+заявок", r"нет\s+клиент", r"нет\s+продаж", r"пока\s+нет",
    r"просто\s+хочу", r"только\s+начина", r"еще\s+не\s+запус", r"нет\s+бизнес",
    r"просто\s+(?:по)?смотр", r"просто\s+интересу",
)
# Explicit roleplay / test-drive intent (B2B turn asking to simulate).
_ROLEPLAY_INTENT_PATTERNS = (
    r"отыгра", r"сыгра", r"будь\s+продавц", r"режим\s+продавца", r"в\s+роли\s+продавц",
    r"как\s+(?:это\s+)?буд(?:ет|е)\s+у\s+меня", r"как\s+бот\s+буд", r"представь\s+что\s+ты",
    r"побудь", r"отыграем",
)
# Anti-fit DIY / open-source intent (technical do-it-myself, below minimum budget).
_DIY_PATTERNS = (
    r"open-?source", r"опенсорс", r"исходник", r"сам\s+развер", r"сам\s+напиш",
    r"сам\s+сдела", r"сам\s+подключ", r"своими\s+руками", r"бесплатн",
)


def _match_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def analyze_signals(message: str, chat_history: list | None = None) -> dict:
    """Return detected profile signals + behavior flags for the current message.

    ``chat_history`` is accepted for interface stability but Phase 1 heuristics only read
    the current message (history-aware extraction is deferred to the LLM extractor, Phase 3).
    """
    text = _normalize(message)
    profile_signals: dict[str, object] = {}
    list_signals: dict[str, list] = {}

    if not text:
        return {"profile_signals": {}, "list_signals": {}, "behavior": _empty_behavior(), "has_business_signal": False}

    # owner involvement (inferred)
    if _match_any(_OWNER_PATTERNS, text):
        profile_signals["owner_involved"] = new_field_value(
            True, confidence=0.7, source_text=message[:160], extraction_type="inferred"
        )

    # operators / team size: "5 менеджеров", "3 сотрудника", "команда из 4"
    m = re.search(r"(\d{1,3})\s*(?:менеджер|сотрудник|оператор|продавц|чел)", text)
    if not m:
        m = re.search(r"команд[аые]\s+из\s+(\d{1,3})", text)
    if m:
        profile_signals["operators_count"] = new_field_value(
            int(m.group(1)), confidence=0.85, source_text=m.group(0), extraction_type="explicit"
        )

    # lead volume: "100 заявок в день", "20 лидов", "50 обращений в неделю"
    lv = re.search(r"(\d{1,5})\s*(?:заявок|лид|обращени|клиент|сообщени)", text)
    if lv:
        profile_signals["lead_volume_count"] = new_field_value(
            int(lv.group(1)), confidence=0.8, source_text=lv.group(0), extraction_type="explicit"
        )
        period = "day" if re.search(r"в\s+день|ежедневн|/день|в\s+сутки", text) else (
            "week" if re.search(r"в\s+недел", text) else (
                "month" if re.search(r"в\s+месяц", text) else None
            )
        )
        if period:
            profile_signals["lead_volume_period"] = new_field_value(
                period, confidence=0.7, source_text=lv.group(0), extraction_type="explicit"
            )

    # average check: "чек 30к", "средний чек 50000", "по 25 тыс"
    ac = re.search(r"чек[а-я]*\s*(?:в\s*)?(\d{1,3})\s*(?:к\b|тыс|000)", text) or \
        re.search(r"(\d{4,7})\s*(?:тенге|руб|₸|р\b)", text)
    if ac:
        profile_signals["average_check"] = new_field_value(
            ac.group(1), confidence=0.7, source_text=ac.group(0), extraction_type="explicit"
        )

    # paid traffic signal -> data_sources / urgency hint stored as pain marker
    if re.search(r"платн[ыо][йе]\s+трафик|таргет|директ\s+реклам|реклам", text):
        list_signals.setdefault("data_sources_available", []).append("paid_traffic")

    # CRM / tracking
    for kw, label in _CRM_KEYWORDS.items():
        if kw in text:
            profile_signals["crm_or_tracking_tool"] = new_field_value(
                label, confidence=0.8, source_text=kw, extraction_type="explicit"
            )
            break

    # lead channels (list)
    channels: list[str] = []
    for kw, label in _CHANNEL_KEYWORDS.items():
        if kw in text and label not in channels:
            channels.append(label)
    if channels:
        list_signals["lead_channels"] = channels

    # pains (list)
    pains: list[str] = []
    for kw, label in _PAIN_KEYWORDS.items():
        if kw in text and label not in pains:
            pains.append(label)
    if pains:
        list_signals["main_pains"] = pains

    # integration needs (list)
    integrations: list[str] = []
    for kw, label in _INTEGRATION_KEYWORDS.items():
        if kw in text and label not in integrations:
            integrations.append(label)
    if integrations:
        list_signals["integration_needs"] = integrations

    behavior = _empty_behavior()
    behavior["asked_price"] = _match_any(_PRICE_PATTERNS, text)
    behavior["asked_for_demo"] = _match_any(_DEMO_PATTERNS, text)
    behavior["asked_how_it_works"] = _match_any(_HOW_PATTERNS, text)
    behavior["explicit_commercial_intent"] = behavior["asked_price"]
    behavior["irritated_by_questions"] = _match_any(_IRRITATED_PATTERNS, text)
    if behavior["irritated_by_questions"]:
        behavior["friction_signals"].append("too_many_questions")
    behavior["low_fit_signal"] = _match_any(_LOW_FIT_PATTERNS, text)
    behavior["diy_signal"] = _match_any(_DIY_PATTERNS, text)
    behavior["roleplay_intent"] = _match_any(_ROLEPLAY_INTENT_PATTERNS, text)

    has_business_signal = bool(profile_signals or list_signals or pains or integrations)

    return {
        "profile_signals": profile_signals,
        "list_signals": list_signals,
        "behavior": behavior,
        "has_business_signal": has_business_signal,
    }


def _empty_behavior() -> dict:
    return {
        "asked_price": False,
        "asked_how_it_works": False,
        "asked_for_demo": False,
        "explicit_commercial_intent": False,
        "irritated_by_questions": False,
        "low_fit_signal": False,
        "diy_signal": False,
        "roleplay_intent": False,
        "friction_signals": [],
    }


def should_run_llm_extraction(message: str, chat_history: list | None = None) -> tuple[bool, str | None]:
    """Heuristic-first gate (clarification #2).

    Returns ``(should_run, skip_reason)``. On short acknowledgements ("ок", "да", "ага")
    extraction is skipped. Note: Phase 1 never actually calls the LLM — this only decides the
    logged skip reason.
    """
    text = _normalize(message)
    if not text:
        return False, "empty_message"

    if text in _LOW_SIGNAL_TOKENS or len(text) < 3:
        return False, "low_signal"

    analysis = analyze_signals(message, chat_history)
    behavior = analysis["behavior"]
    if analysis["has_business_signal"] or behavior["asked_price"] or behavior["asked_for_demo"]:
        return True, None

    # No strong heuristic signal, but message is non-trivial -> would be ambiguous for LLM.
    if len(text) >= 25:
        return True, None

    return False, "low_signal"
