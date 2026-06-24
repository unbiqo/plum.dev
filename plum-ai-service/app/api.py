from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from .gemini_service import GeminiService
from .gemini_quota import GeminiQuotaExhausted
from .schemas import ChatAttachment, ChatHistoryMessage, ChatRequest, ChatResponse, ProductCard, Route
from .supabase_service import SupabaseService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

SESSION_TIMEOUT = timedelta(hours=6)
RATE_LIMIT_MAX_REQUESTS = 7
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
RATE_LIMIT_DETAIL = (
    "\u0412\u044b \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442\u0435 "
    "\u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f "
    "\u0441\u043b\u0438\u0448\u043a\u043e\u043c \u0447\u0430\u0441\u0442\u043e. "
    "\u041b\u0438\u043c\u0438\u0442 - 7 "
    "\u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0439 \u0432 "
    "\u043c\u0438\u043d\u0443\u0442\u0443."
)

GENERATION_FALLBACK_MARKERS = (
    "Давайте продолжим спокойно. По этому вопросу отвечу только по данным базы",
    "Напишите, какой процесс или канал продаж хотите автоматизировать",
    "Могу продолжить без лишней теории: по AI-проекту стоимость нужно считать по вводным",
)

DOCUMENT_REQUEST_PATTERNS = (
    r"\bcases?\b",
    r"\bportfolio\b",
    r"\bdemo\b",
    r"\bexample?s?\b",
    r"кейс",
    r"портфолио",
    r"пример",
    r"примеры\s+работ",
    r"демо",
    r"демонстрац",
    r"показать\s+работ",
    r"что\s+делал",
    r"результат",
)

DOCUMENTS_SITE_ANSWER = (
    "Кейсы, портфолио и демо будут собраны на сайте: https://your-portfolio.dev/."
    "\n\nМогу пока быстро сориентировать, какой сценарий AI-автоматизации подойдет под вашу воронку — что сейчас важнее автоматизировать?"
)

START_GREETING_ANSWER = (
    "Привет! На связи ИИ-помощник Plum Dev 🚀 Мы делаем умных роботов-продавцов с полной интеграцией в ваш бизнес.\n"
    "Я умею не просто слать автоответы, а реально дожимать сделки. Попробуем?\n\n"
    "💡 Кликни на команду /roleplay — Я мгновенно включу режим продавца и покажу, как ИИ будет общаться с твоими клиентами.\n"
    "📈 Или просто напиши мне свои боли в продажах, и я на пальцах разложу, как нейросети окупят себя за первую неделю.\n\n"
    "С чего начнем: /roleplay или разберем вашу воронку?"
)

DIALOG_STATE_KEY = "dialog_state"
VALID_SERVICE_FOCUS = {"base", "cart", "agent"}
ROLEPLAY_AWAITING_CONTEXT_KEY = "roleplay_demo_awaiting_context"
ROLEPLAY_CONTEXT_SUMMARY_KEY = "roleplay_demo_context_summary"
ROLEPLAY_CONTEXT_SOURCE_KEY = "roleplay_demo_context_source"
ROLEPLAY_CONTEXT_WAIT_COUNT_KEY = "roleplay_demo_context_wait_count"
ROLEPLAY_NO_FILE_FALLBACK_KEY = "roleplay_demo_no_file_fallback"
BUYING_MILESTONE_KEYS = {
    "pain_expressed",
    "demo_activated",
    "price_exposed",
    "close_consented",
}

CONTACT_COLLECTION_PATTERNS = (
    r"имя",
    r"сфера\s+бизнес",
    r"ниша",
    r"сайт",
    r"instagram",
    r"инст",
    r"ссылка",
    r"телефон",
    r"контакт",
)
CHECKOUT_COMPLETED_PATTERNS = (
    r"заказ\s+оформлен",
    r"заказ\s+принят",
    r"заявк[ау]\s+принял",
    r"заявк[ау]\s+оформ",
    r"передал[аи]?\s+.*менедж",
    r"отправил[аи]?\s+.*менедж",
)
CONTACT_PLACEHOLDER_PATTERNS = (
    r"^\s*(написал[аи]?|отправил[аи]?|лови|да|ок|ага|угу|готово|\+|сейчас|уже)\s*[.!)]*\s*$",
)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\s().-]*){7,}")

# Russian number words used to parse phone numbers written as text
_RU_HUNDREDS: dict[str, int] = {
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}
_RU_TENS: dict[str, int] = {
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
}
_RU_ONES_MAP: dict[str, int] = {
    "ноль": 0, "нуль": 0, "один": 1, "одна": 1, "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19,
}
_ALL_DIGIT_WORDS: frozenset[str] = frozenset(_RU_HUNDREDS) | frozenset(_RU_TENS) | frozenset(_RU_ONES_MAP)

PROJECT_DETAIL_PATTERN = re.compile(
    r"(?:сфера|ниша|бизнес|сайт|instagram|инст|crm|срм|воронк|заявк|лид|бот|агент|автоматизац|интеграц)",
    re.IGNORECASE,
)
AI_SERVICE_IMAGE_URLS: dict[str, str] = {}


async def send_platform_typing_indicator(platform: str, user_id: str) -> None:
    normalized_platform = (platform or "").strip().lower()
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return

    try:
        if normalized_platform == "telegram":
            token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
            if not token:
                logger.debug("Telegram typing indicator skipped: bot token is not configured in AI service")
                return
            await asyncio.to_thread(
                _post_form_urlencoded,
                f"https://api.telegram.org/bot{token}/sendChatAction",
                {
                    "chat_id": normalized_user_id,
                    "action": "typing",
                },
                {},
            )
            return

        if normalized_platform == "instagram":
            access_token = os.getenv("META_PAGE_ACCESS_TOKEN") or os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN")
            endpoint = os.getenv(
                "INSTAGRAM_MESSAGES_ENDPOINT",
                "https://graph.facebook.com/v19.0/me/messages",
            )
            if not access_token:
                logger.debug("Instagram typing indicator skipped: Meta access token is not configured")
                return
            await asyncio.to_thread(
                _post_json,
                f"{endpoint}?access_token={urllib_parse.quote(access_token)}",
                {
                    "recipient": {"id": normalized_user_id},
                    "sender_action": "typing_on",
                },
                {},
            )
            return

        if normalized_platform == "whatsapp":
            endpoint = os.getenv("WHATSAPP_TYPING_ENDPOINT")
            token = os.getenv("WHATSAPP_ACCESS_TOKEN")
            if not endpoint:
                logger.debug("WhatsApp typing indicator skipped: provider endpoint is not configured")
                return
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            await asyncio.to_thread(
                _post_json,
                endpoint,
                {
                    "recipient": normalized_user_id,
                    "sender_action": "typing_on",
                },
                headers,
            )
            return

        logger.debug("Typing indicator skipped for platform=%s", platform)
    except Exception:
        logger.exception("Failed to send typing indicator for platform=%s user_id=%s", platform, user_id)


def _post_form_urlencoded(url: str, data: dict[str, str], headers: dict[str, str]) -> None:
    body = urllib_parse.urlencode(data).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            **headers,
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=3):
        return


def _post_json(url: str, data: dict[str, object], headers: dict[str, str]) -> None:
    body = json.dumps(data).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            **headers,
        },
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=3):
        return


def _has_explicit_commercial_intent(
    message: str,
    chat_history: list[ChatHistoryMessage] | None = None,
) -> bool:
    normalized = message.casefold()
    commercial_patterns = (
        r"\bprice\b",
        r"\bcost\b",
        r"\bbuy\b",
        r"\border\b",
        r"\bcheckout\b",
        r"\bpay\b",
        r"\bshop\b",
        r"\bavailable\b",
        r"\bavailability\b",
        r"\bcart\b",
        r"\breserve\b",
        r"\bshipping\b",
        r"\bdelivery\b",
        r"\bdiscount\b",
        r"\u0446\u0435\u043d[ауые]",
        r"\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442",
        r"\u0441\u043a\u043e\u043b\u044c\u043a\u043e\s+\u0441\u0442\u043e\u0438\u0442",
        r"\u043f\u0440\u0430\u0439\u0441",
        r"\u043a\u0443\u043f\u0438\u0442\u044c",
        r"\u0437\u0430\u043a\u0430\u0437\u0430\u0442\u044c",
        r"\u043e\u0444\u043e\u0440\u043c\u0438\u0442\u044c",
        r"\u043e\u043f\u043b\u0430\u0442",
        r"\u0432\s+\u043d\u0430\u043b\u0438\u0447\u0438\u0438",
        r"\u043d\u0430\u043b\u0438\u0447\u0438\u0435",
        r"\u0435\u0441\u0442\u044c\s+\u0432\s+\u043d\u0430\u043b\u0438\u0447\u0438\u0438",
        r"\u043f\u0440\u043e\u0434\u0430[её]\u0442\u0435",
        r"\u0431\u0435\u0440\u0443",
        r"\u043a\u043e\u0440\u0437\u0438\u043d",
        r"\u0434\u043e\u0441\u0442\u0430\u0432\u043a",
        r"\u0441\u043a\u0438\u0434\u043a",
    )
    if any(re.search(pattern, normalized) for pattern in commercial_patterns):
        return True

    return False


def _last_assistant_message(chat_history: list[ChatHistoryMessage]) -> str:
    for item in reversed(chat_history):
        if item.role == "assistant":
            return item.content
    return ""


def _detect_roleplay_demo_context(
    *,
    message: str,
    chat_history: list[ChatHistoryMessage],
    dialog_state: dict[str, object],
) -> dict[str, object]:
    normalized = message.casefold().replace("ё", "е")
    was_active = bool(dialog_state.get("roleplay_demo_active"))
    was_waiting_for_context = bool(dialog_state.get(ROLEPLAY_AWAITING_CONTEXT_KEY))

    if (was_active or was_waiting_for_context) and _is_roleplay_demo_exit_request(normalized):
        return {"active": False, "exit": True}

    explicit_request = _is_explicit_roleplay_command(message)

    active = explicit_request or was_active or was_waiting_for_context
    if not active:
        return {"active": False}

    topic = _extract_roleplay_demo_topic(message)
    if not topic:
        topic = str(dialog_state.get("roleplay_demo_topic") or "").strip()

    return {
        "active": True,
        "topic": topic,
        "new_request": explicit_request,
    }


def _is_explicit_roleplay_command(message: str) -> bool:
    normalized = message.strip().casefold().replace("ё", "е")
    return bool(
        re.search(r"^/roleplay(?:@\w+)?(?:\s|$)", normalized)
        or re.search(r"\b(?:отыграй|сыграй|играй)\s+роль\b", normalized)
        or re.search(r"\b(?:представь|представьте),?\s+что\s+ты\b", normalized)
        or re.search(r"\bбудь\s+(?:продавц|менеджер|консультант)", normalized)
        or re.search(r"\bведи\s+диалог\s+будто\s+ты\b", normalized)
        or re.search(r"\b(?:включи|запусти)\s+(?:режим\s+)?(?:продавц|менеджер|консультант|ролев)", normalized)
        # B2C simulation: "Я твой клиент..., погнали" style roleplay invitations
        or re.search(r"\bя\s+(?:твой|ваш)\s+клиент\b.{0,60}\b(?:погнали|поехали|начинаем|давай|вперед|старт)\b", normalized)
        or re.search(r"\b(?:погнали|поехали)\b.{0,40}\bя\s+(?:твой|ваш)\s+клиент\b", normalized)
        or re.search(r"\b(?:я\s+)?в\s+роли\s+(?:клиент|покупател)\b", normalized)
        or re.search(r"\bпишу\s+(?:как|будто|в\s+роли)\s+(?:клиент|покупател)\b", normalized)
    )


def _is_roleplay_demo_exit_request(normalized_message: str) -> bool:
    return bool(
        re.search(
            r"\b(?:выйд(?:и|ем|ите)|выход(?:и|ите)?|выйти)\s+из\s+рол[иь]\b",
            normalized_message,
        )
        or re.search(r"\bсними(?:те)?\s+маск", normalized_message)
        or re.search(r"\bхватит\s+(?:играть|ролев)", normalized_message)
        or re.search(r"\b(?:стоп|закончи(?:ть|м)?)\s+(?:роль|игру|демо)", normalized_message)
        or re.search(r"\bдавай(?:те)?\s+к\s+делу\b", normalized_message)
        or re.search(r"\bя\s+готов(?:а)?\s+купить\b", normalized_message)
        or re.search(r"\bверни(?:сь|тесь)?\s+к\s+(?:ии|ai|plum|плам|бот|агент)", normalized_message)
        or re.search(r"\bя\s+про\s+(?:ии|ai)\s*-?\s*агент", normalized_message)
        or re.search(r"\b(?:ваш|твой)\s+(?:ии|ai|бот|агент)", normalized_message)
        or re.search(r"\b(?:как|сколько|что)\b.{0,80}\b(?:разработ|имплемент|внедр|собрать|сделать)\b.{0,80}\b(?:бот|агент|ии|ai)", normalized_message)
        or re.search(
            r"\bсколько\s+(?:будет\s+)?стоить\s+(?:сделать|собрать|внедрить)\s+так(?:ой|ого)\s+(?:бот|агент)",
            normalized_message,
        )
        or (
            re.search(r"\bвернемся\b", normalized_message)
            and re.search(r"plum|плам|ии|бот|агент|автоматизац|проект|расчет", normalized_message)
        )
    )


def _extract_roleplay_demo_topic(message: str) -> str:
    normalized = " ".join(message.strip().split())
    patterns = (
        r"продай\s+мне\s+(?P<topic>[^?.!,]+)",
        r"роль\s+(?:менеджера|продавца|консультанта)\s+(?:по|в)?\s*(?P<topic>[^?.!,]+)",
        r"продавца\s+(?P<topic>[^?.!,]+)",
        r"продавец\s+(?P<topic>[^?.!,]+)",
        r"будто\s+ты\s+продавец\s+(?P<topic>[^?.!,]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            topic = match.group("topic").strip(" .,!?:;\"'")
            if topic:
                return topic[:80]
    return ""


def _format_roleplay_demo_instruction(roleplay_demo: dict[str, object]) -> str:
    if not roleplay_demo.get("active"):
        return ""

    topic = str(roleplay_demo.get("topic") or "").strip()
    topic_line = f"Current demo niche/product: {topic}." if topic else "Infer the demo niche/product from the user's latest message."
    return (
        "ROLEPLAY DEMO MODE IS ACTIVE.\n"
        f"{topic_line}\n"
        "Ignore Plum Dev sales flow, packages, prices, checkout, RAG facts, and previous AI-service offers for this answer. "
        "Do not mention Base/Custom, audits, project estimates, $300, AI-assistant pricing, CRM handoff, or Plum Dev unless the user explicitly exits the roleplay.\n"
        "Act as a smart seller in the user's requested niche. If the user just switched niche, immediately create a short roleplay scene in that niche. "
        "If the user gave an objection or question, answer inside the roleplay as that seller."
    )


def _format_roleplay_exit_bridge_instruction(roleplay_demo: dict[str, object]) -> str:
    if not roleplay_demo.get("exit"):
        return ""

    return (
        "Roleplay demo has just ended. Use the normal Plum Dev AI-architect sales mode for this answer. "
        "Start exactly with: \"Маску снял, вернулся в режим архитектора Plum Dev.\" "
        "Then answer the user's latest question about automation, bot cost, or the next practical step. "
        "If the user refers to 'такой бот' or the demo, use the recent roleplay messages as the example of the behavior they want to build. "
        "Do not continue the previous seller role."
    )


def _clear_roleplay_state(dialog_state: dict[str, object]) -> None:
    dialog_state["roleplay_demo_active"] = False
    for key in (
        "roleplay_demo_topic",
        ROLEPLAY_AWAITING_CONTEXT_KEY,
        ROLEPLAY_CONTEXT_SUMMARY_KEY,
        ROLEPLAY_CONTEXT_SOURCE_KEY,
        ROLEPLAY_CONTEXT_WAIT_COUNT_KEY,
        ROLEPLAY_NO_FILE_FALLBACK_KEY,
    ):
        dialog_state.pop(key, None)


def _has_supported_roleplay_attachment(attachments: list[ChatAttachment]) -> bool:
    return any(
        (attachment.base64_data or attachment.url)
        and re.search(
            r"^(?:image/|application/pdf|text/|application/vnd\.openxmlformats-officedocument|application/msword)",
            attachment.mime_type,
            re.IGNORECASE,
        )
        for attachment in attachments
    )


def _roleplay_context_request_answer(topic: str, *, reminder: bool = False) -> str:
    if reminder:
        return (
            "Я все еще жду вводные для тест-драйва.\n\n"
            "Можно прислать PDF, скрин прайса или короткое описание компании текстом. "
            "Если файла нет, напишите «без файла» — начну демо на общих знаниях."
        )
    return (
        "Отлично, переключаюсь в режим тест-драйва! 🎭\n\n"
        "Чтобы я не гадал и общался именно так, как нужно вашему бизнесу, дайте мне немного вводных. "
        "Вы можете сделать любое из трех действий:\n"
        "1️⃣ Прикрепить PDF-каталог, презентацию или презентационный документ.\n"
        "2️⃣ Скинуть скриншот или картинку вашего прайс-листа с ценами.\n"
        "3️⃣ Просто написать текстом описание вашей компании в свободной форме.\n\n"
        "Пример хорошего текстового описания:\n"
        "\"Компания [Название], продаем [Товар или Услугу] оптом, средний чек [Цена], "
        "клиенты чаще всего уходят после того, как узнают стоимость доставки\".\n\n"
        "Жду ваш файл или текст — как только получу, сразу включу маску вашего менеджера по продажам!"
    )


def _build_price_override_answer() -> str:
    return (
        "По Plum Dev ориентир такой: базовый ИИ-ассистент для приема и дожима заявок — от $300.\n\n"
        "Если нужно собрать все вместе — база знаний, сценарии продаж, интеграции и передачу заявок менеджеру — "
        "сначала фиксируем спецификацию, чтобы не называть цену с потолка.\n\n"
        "Давайте соберу расчет: какие 2-3 действия бот должен делать вместо менеджера?"
    )


def _is_roleplay_text_context(message: str) -> bool:
    normalized = message.strip()
    if len(normalized) < 60:
        return False
    lowered = normalized.casefold().replace("ё", "е")
    if re.search(r"^/roleplay(?:@\w+)?\s*$", lowered):
        return False
    return bool(
        re.search(r"компан|прода|услуг|товар|цена|стоимост|средн|чек|клиент|доставк|услов", lowered)
    )


def _should_start_roleplay_without_file(message: str, wait_count: int) -> bool:
    normalized = message.casefold().replace("ё", "е")
    return wait_count >= 2 or bool(
        re.search(r"\b(?:без\s+файла|нет\s+файла|файла\s+нет|давай\s+без|начинай|погнали|играй)\b", normalized)
    )


def _roleplay_attachment_source(attachments: list[ChatAttachment]) -> str:
    names = [
        attachment.filename or attachment.mime_type
        for attachment in attachments
        if attachment.base64_data or attachment.url
    ]
    return ", ".join(names[:3])[:240]


def _format_roleplay_file_context_instruction(dialog_state: dict[str, object]) -> str:
    context = str(dialog_state.get(ROLEPLAY_CONTEXT_SUMMARY_KEY) or "").strip()
    if not context:
        return ""
    return (
        "Temporary roleplay file context for this session only:\n"
        f"{context}\n"
        "Use this context for concrete roleplay facts. Do not treat it as Plum Dev knowledge base."
    )


def _format_buying_readiness_instruction(dialog_state: dict[str, object]) -> str:
    if dialog_state.get("contact_phone_collected"):
        return (
            "HIGHEST PRIORITY CONTACT COMPLETION OVERRIDE: a valid phone/WhatsApp contact is already collected. "
            "It is categorically forbidden to ask which WhatsApp number to use, ask for a phone again, or request contact details again. "
            "Close the loop with a final confirmation: the number is recorded, the specification is being passed to a manager, and they will contact the client in WhatsApp soon."
        )
    traffic_done_rule = (
        "ВНИМАНИЕ: Этап квалификации трафика официально ЗАВЕРШЕН. "
        "Запрещено спрашивать откуда идут клиенты. "
        "Твой единственный фокус — закрытие на расчет спецификации. "
        "Do not ask about Instagram, WhatsApp, site, channel, traffic source, lead source, or where clients come from."
    )
    if dialog_state.get("close_consented"):
        return (
            "HIGHEST PRIORITY BUYING READINESS OVERRIDE: close_consented is already true. "
            f"{traffic_done_rule} "
            "Answer the current question, then close toward project specification calculation or handoff."
        )
    if dialog_state.get("price_exposed"):
        return (
            "HIGHEST PRIORITY BUYING READINESS OVERRIDE: price_exposed is already true. "
            f"{traffic_done_rule} "
            "Your only commercial focus is closing toward project specification calculation. Answer the current question, then move to: what exactly should be included in the bot/specification."
        )
    if dialog_state.get("demo_activated"):
        return (
            "HIGHEST PRIORITY BUYING READINESS OVERRIDE: demo_activated is already true. "
            f"{traffic_done_rule} "
            "Tie the answer back to what the user saw in the demo and guide toward calculating/specifying a similar bot."
        )
    if dialog_state.get("pain_expressed"):
        return (
            "Buying readiness: pain_expressed is true. Explain the business value simply, with quick ROI logic, and offer /roleplay as the practical test."
        )
    return ""


async def _handle_roleplay_context_gate(
    *,
    gemini: GeminiService,
    supabase: SupabaseService,
    payload: ChatRequest,
    effective_history: list[ChatHistoryMessage],
    session_metadata: dict[str, Any],
    dialog_state: dict[str, object],
    roleplay_demo: dict[str, object],
) -> ChatResponse | None:
    entering_or_waiting = bool(
        roleplay_demo.get("new_request")
        or roleplay_demo.get("router_entry")
        or dialog_state.get(ROLEPLAY_AWAITING_CONTEXT_KEY)
    )
    if not entering_or_waiting:
        return None

    topic = str(roleplay_demo.get("topic") or dialog_state.get("roleplay_demo_topic") or "").strip()
    attachments = payload.attachments
    dialog_state["demo_activated"] = True

    if _has_supported_roleplay_attachment(attachments):
        try:
            context_summary = await gemini.extract_roleplay_context_from_attachment(
                message=payload.message,
                topic=topic,
                attachments=attachments,
            )
        except Exception:
            logger.exception("Failed to extract roleplay context from attachment")
            context_summary = ""

        if context_summary:
            dialog_state["roleplay_demo_active"] = True
            dialog_state["roleplay_demo_topic"] = topic
            dialog_state[ROLEPLAY_AWAITING_CONTEXT_KEY] = False
            dialog_state[ROLEPLAY_CONTEXT_SUMMARY_KEY] = context_summary[:5000]
            dialog_state[ROLEPLAY_CONTEXT_SOURCE_KEY] = _roleplay_attachment_source(attachments)
            dialog_state[ROLEPLAY_CONTEXT_WAIT_COUNT_KEY] = 0
            dialog_state[ROLEPLAY_NO_FILE_FALLBACK_KEY] = False
            session_metadata[DIALOG_STATE_KEY] = dialog_state
            await supabase.upsert_chat_session_metadata(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                metadata=session_metadata,
            )
            return None

        answer = (
            "Файл получил, но не смог надежно прочитать данные. "
            "Пришлите, пожалуйста, более четкий скрин/документ или напишите «без файла», и я начну демо на общих знаниях."
        )
        dialog_state[ROLEPLAY_AWAITING_CONTEXT_KEY] = True
        session_metadata[DIALOG_STATE_KEY] = dialog_state
        await supabase.upsert_chat_session_metadata(
            instance_id=payload.instance_id,
            channel=payload.channel,
            chat_id=payload.chat_id,
            metadata=session_metadata,
        )
        return await _build_and_log_roleplay_gate_response(
            supabase=supabase,
            payload=payload,
            answer=answer,
            metadata={
                "roleplay_context_file_failed": True,
                "roleplay_demo_topic": topic,
            },
        )

    if _is_roleplay_text_context(payload.message):
        try:
            context_summary = await gemini.extract_roleplay_context_from_text(
                message=payload.message,
                topic=topic,
            )
        except Exception:
            logger.exception("Failed to extract roleplay context from text")
            context_summary = payload.message

        dialog_state["roleplay_demo_active"] = True
        dialog_state["roleplay_demo_topic"] = topic
        dialog_state[ROLEPLAY_AWAITING_CONTEXT_KEY] = False
        dialog_state[ROLEPLAY_CONTEXT_SUMMARY_KEY] = (context_summary or payload.message)[:5000]
        dialog_state[ROLEPLAY_CONTEXT_SOURCE_KEY] = "text_description"
        dialog_state[ROLEPLAY_CONTEXT_WAIT_COUNT_KEY] = 0
        dialog_state[ROLEPLAY_NO_FILE_FALLBACK_KEY] = False
        session_metadata[DIALOG_STATE_KEY] = dialog_state
        await supabase.upsert_chat_session_metadata(
            instance_id=payload.instance_id,
            channel=payload.channel,
            chat_id=payload.chat_id,
            metadata=session_metadata,
        )
        return None

    wait_count = int(dialog_state.get(ROLEPLAY_CONTEXT_WAIT_COUNT_KEY) or 0)
    if _should_start_roleplay_without_file(payload.message, wait_count):
        dialog_state["roleplay_demo_active"] = True
        dialog_state["roleplay_demo_topic"] = topic
        dialog_state[ROLEPLAY_AWAITING_CONTEXT_KEY] = False
        dialog_state[ROLEPLAY_CONTEXT_SUMMARY_KEY] = ""
        dialog_state[ROLEPLAY_CONTEXT_SOURCE_KEY] = ""
        dialog_state[ROLEPLAY_CONTEXT_WAIT_COUNT_KEY] = wait_count
        dialog_state[ROLEPLAY_NO_FILE_FALLBACK_KEY] = True
        session_metadata[DIALOG_STATE_KEY] = dialog_state
        await supabase.upsert_chat_session_metadata(
            instance_id=payload.instance_id,
            channel=payload.channel,
            chat_id=payload.chat_id,
            metadata=session_metadata,
        )
        return None

    wait_count += 1
    dialog_state["roleplay_demo_active"] = False
    dialog_state["roleplay_demo_topic"] = topic
    dialog_state[ROLEPLAY_AWAITING_CONTEXT_KEY] = True
    dialog_state[ROLEPLAY_CONTEXT_WAIT_COUNT_KEY] = wait_count
    session_metadata[DIALOG_STATE_KEY] = dialog_state
    await supabase.upsert_chat_session_metadata(
        instance_id=payload.instance_id,
        channel=payload.channel,
        chat_id=payload.chat_id,
        metadata=session_metadata,
    )
    return await _build_and_log_roleplay_gate_response(
        supabase=supabase,
        payload=payload,
        answer=_roleplay_context_request_answer(topic, reminder=wait_count > 1),
        metadata={
            "roleplay_awaiting_context_file": True,
            "roleplay_demo_topic": topic,
            "roleplay_context_wait_count": wait_count,
        },
    )


async def _build_and_log_roleplay_gate_response(
    *,
    supabase: SupabaseService,
    payload: ChatRequest,
    answer: str,
    metadata: dict[str, Any],
) -> ChatResponse:
    answer = _format_messenger_answer(answer)
    response = ChatResponse(
        route=Route.roleplay,
        routes=[Route.roleplay],
        answer=answer,
        checkout=False,
        metadata={
            "rag_context_found": False,
            "commercial_context_used": False,
            **metadata,
        },
    )
    await supabase.log_chat(
        channel=payload.channel,
        chat_id=payload.chat_id,
        instance_id=payload.instance_id,
        message=payload.message or "[attachment]",
        ai_response=response.answer,
        routes=response.routes,
        metadata=_build_log_metadata(response),
    )
    return response


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> ChatResponse:
    gemini: GeminiService = request.app.state.gemini
    supabase: SupabaseService = request.app.state.supabase

    try:
        _check_rate_limit(payload.channel, payload.chat_id)
        asyncio.create_task(
            send_platform_typing_indicator(payload.channel, payload.chat_id)
        )
        tenant_settings = await supabase.get_tenant_settings(
            instance_id=payload.instance_id,
        )

        if payload.reset_context:
            await supabase.clear_conversation_state(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
            )

        last_message_at = await supabase.get_last_message_at(
            instance_id=payload.instance_id,
            channel=payload.channel,
            chat_id=payload.chat_id,
        )
        is_new_session = payload.reset_context or _is_new_session(last_message_at)
        logged_history: list[ChatHistoryMessage] = []
        if not is_new_session:
            logged_history = await supabase.fetch_recent_chat_history(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                limit=gemini.settings.max_history_messages,
            )
        effective_history = _build_effective_history(
            logged_history=logged_history,
            payload_history=payload.chat_history,
            max_messages=gemini.settings.max_history_messages,
            reset_context=payload.reset_context,
        )
        effective_history = _strip_generation_fallback_history(effective_history)
        session_metadata = await supabase.get_chat_session_metadata(
            instance_id=payload.instance_id,
            channel=payload.channel,
            chat_id=payload.chat_id,
        )
        fact_scan_history = effective_history
        stored_client_facts = session_metadata.get("client_facts")
        if not payload.reset_context and not stored_client_facts:
            server_fact_scan_history = await supabase.fetch_fact_scan_history(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                limit=200,
            )
            fact_scan_history = _merge_chat_history(
                server_fact_scan_history,
                payload.chat_history,
                max(gemini.settings.max_history_messages, 200),
            )
        client_facts = _merge_client_facts_for_request(
            gemini=gemini,
            session_metadata=session_metadata,
            fact_scan_history=fact_scan_history,
            message=payload.message,
        )
        session_metadata["client_facts"] = client_facts
        dialog_state = _build_dialog_state_for_request(
            session_metadata=session_metadata,
            chat_history=effective_history,
            message=payload.message,
            client_facts=client_facts,
        )
        roleplay_demo = _detect_roleplay_demo_context(
            message=payload.message,
            chat_history=effective_history,
            dialog_state=dialog_state,
        )
        if roleplay_demo.get("exit"):
            _clear_roleplay_state(dialog_state)
        elif roleplay_demo.get("active"):
            dialog_state["roleplay_demo_active"] = True
            if roleplay_demo.get("topic"):
                dialog_state["roleplay_demo_topic"] = str(roleplay_demo["topic"])
        session_metadata[DIALOG_STATE_KEY] = dialog_state
        if client_facts or roleplay_demo.get("active") or roleplay_demo.get("exit"):
            await supabase.upsert_chat_session_metadata(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                metadata=session_metadata,
            )
        roleplay_gate_response = await _handle_roleplay_context_gate(
            gemini=gemini,
            supabase=supabase,
            payload=payload,
            effective_history=effective_history,
            session_metadata=session_metadata,
            dialog_state=dialog_state,
            roleplay_demo=roleplay_demo,
        )
        if roleplay_gate_response is not None:
            return roleplay_gate_response
        memory_context = ""

        if payload.reset_context and _is_plain_greeting(payload.message):
            response = ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=_format_messenger_answer(START_GREETING_ANSWER),
                checkout=False,
                metadata={
                    "start_greeting": True,
                    "rag_context_found": False,
                    "tenant_found": bool(tenant_settings),
                    "client_facts": client_facts,
                    "server_history_used": bool(logged_history),
                    "logged_history_messages": len(logged_history),
                    "payload_history_messages": len(payload.chat_history),
                    "effective_history_messages": len(effective_history),
                },
            )
            await supabase.log_chat(
                channel=payload.channel,
                chat_id=payload.chat_id,
                instance_id=payload.instance_id,
                message=payload.message,
                ai_response=response.answer,
                routes=response.routes,
                metadata=_build_log_metadata(response),
            )
            return response

        if _is_document_request(payload.message):
            response = ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=_format_messenger_answer(DOCUMENTS_SITE_ANSWER),
                checkout=False,
                metadata={
                    "document_request_redirect": True,
                    "rag_context_found": False,
                    "tenant_found": bool(tenant_settings),
                    "client_facts": client_facts,
                    "server_history_used": bool(logged_history),
                    "logged_history_messages": len(logged_history),
                    "payload_history_messages": len(payload.chat_history),
                    "effective_history_messages": len(effective_history),
                },
            )
            await supabase.log_chat(
                channel=payload.channel,
                chat_id=payload.chat_id,
                instance_id=payload.instance_id,
                message=payload.message,
                ai_response=response.answer,
                routes=response.routes,
                metadata=_build_log_metadata(response),
            )
            return response

        if not roleplay_demo.get("active") and _is_explicit_plum_price_request(payload.message):
            dialog_state["price_exposed"] = True
            dialog_state["close_consented"] = True
            if _is_all_functions_answer(payload.message) or re.search(
                r"все\s+(?:вместе|функц|задач)|полностью|под\s+ключ",
                payload.message.casefold().replace("ё", "е"),
            ):
                dialog_state["automation_goal"] = "all_sales_agent_functions"
            session_metadata[DIALOG_STATE_KEY] = dialog_state
            await supabase.upsert_chat_session_metadata(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                metadata=session_metadata,
            )
            response = ChatResponse(
                route=Route.checkout,
                routes=[Route.checkout],
                answer=_format_messenger_answer(_build_price_override_answer()),
                checkout=False,
                metadata={
                    "price_override": True,
                    "rag_context_found": False,
                    "commercial_context_used": True,
                    "tenant_found": bool(tenant_settings),
                    "client_facts": client_facts,
                    "dialog_state": dialog_state,
                    "server_history_used": bool(logged_history),
                    "logged_history_messages": len(logged_history),
                    "payload_history_messages": len(payload.chat_history),
                    "effective_history_messages": len(effective_history),
                },
            )
            await supabase.log_chat(
                channel=payload.channel,
                chat_id=payload.chat_id,
                instance_id=payload.instance_id,
                message=payload.message,
                ai_response=response.answer,
                routes=response.routes,
                metadata=_build_log_metadata(response),
            )
            return response

        if not is_new_session and _should_use_memory_context(payload, gemini):
            memory_context = await supabase.get_user_memory(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
            )

        stage_transition = _infer_sales_stage_transition_local(
            message=payload.message,
            chat_history=effective_history,
            client_facts=client_facts,
            dialog_state=dialog_state,
        )
        content_followup = _infer_content_followup_local(
            message=payload.message,
            chat_history=effective_history,
        )
        sales_stage = str(stage_transition.get("stage") or "none")
        router_requested_roleplay_exit = bool(roleplay_demo.get("exit"))
        if router_requested_roleplay_exit:
            roleplay_demo = {"active": False, "exit": True, "router_exit": True}
            _clear_roleplay_state(dialog_state)
            session_metadata[DIALOG_STATE_KEY] = dialog_state
            await supabase.upsert_chat_session_metadata(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                metadata=session_metadata,
            )

        roleplay_demo_active = bool(roleplay_demo.get("active"))
        routes = [Route.rag_required]
        if roleplay_demo_active:
            routes = [Route.general]
            stage_transition = {"stage": "none", "commercial_intent": False, "checkout_intent": False}
            content_followup = "none"
            sales_stage = "none"
        if content_followup != "none":
            sales_stage = "none"
        sales_stage = _apply_dialog_state_stage_override(
            sales_stage=sales_stage,
            dialog_state=dialog_state,
            message=payload.message,
        )
        sales_stage = _apply_product_selection_stage_override(
            sales_stage=sales_stage,
            dialog_state=dialog_state,
            message=payload.message,
        )
        commercial_blocked_until_goal = _should_block_commercial_until_goal(
            message=payload.message,
            client_facts=client_facts,
            dialog_state=dialog_state,
            sales_stage=sales_stage,
        )
        if commercial_blocked_until_goal:
            sales_stage = "none"
        has_explicit_commercial_intent = bool(
            stage_transition.get("commercial_intent")
        ) or _has_explicit_commercial_intent(
            payload.message,
            None,
        )
        if content_followup != "none":
            has_explicit_commercial_intent = False
        if commercial_blocked_until_goal:
            has_explicit_commercial_intent = False
        if sales_stage in {"stage_2_comparison", "stage_3_price", "stage_4_checkout"}:
            has_explicit_commercial_intent = True
        has_checkout_close_intent = bool(stage_transition.get("checkout_intent"))
        force_checkout_from_last_price = sales_stage == "stage_4_checkout"
        if sales_stage == "stage_4_checkout":
            sales_stage = "stage_4_checkout"
            has_explicit_commercial_intent = True
            has_checkout_close_intent = True
            routes = [Route.checkout]
        elif sales_stage in {"stage_2_comparison", "stage_3_price"}:
            has_explicit_commercial_intent = True
            has_checkout_close_intent = False
            if Route.checkout not in routes:
                routes = [route for route in routes if route != Route.general]
                routes.append(Route.checkout)
        if Route.checkout in routes and not has_explicit_commercial_intent:
            routes = [route for route in routes if route != Route.checkout]
            if not routes:
                routes = [Route.rag_required]
        if content_followup != "none" and Route.rag_required not in routes:
            routes = [route for route in routes if route != Route.general]
            routes.append(Route.rag_required)
        if roleplay_demo_active:
            routes = [Route.general]
            sales_stage = "none"
            has_explicit_commercial_intent = False
            has_checkout_close_intent = False
            force_checkout_from_last_price = False
        primary_route = _select_primary_route(routes)

        rag_context = ""
        rewritten_query = ""
        commercial_context = ""
        combined_predicted_route: Route | None = None
        combined_json_valid: bool | None = None
        response_instruction = _join_non_empty(
            _format_buying_readiness_instruction(dialog_state),
            _format_content_followup_instruction(content_followup),
            _format_dialog_state_instruction(
                message=payload.message,
                client_facts=client_facts,
                dialog_state=dialog_state,
                sales_stage=sales_stage,
                content_followup=content_followup,
            ),
            _format_roleplay_exit_bridge_instruction(roleplay_demo),
            _format_roleplay_file_context_instruction(dialog_state),
            _format_roleplay_demo_instruction(roleplay_demo),
        )
        checkout_products: list[ProductCard] = []
        selected_product: ProductCard | None = None

        if Route.rag_required in routes:
            if gemini.settings.enable_hyde_rewrite:
                rewritten_query = await gemini.rewrite_query_hyde(
                    payload.message,
                    system_prompt=tenant_settings.get("hyde_system_prompt", ""),
                )
            else:
                rewritten_query = payload.message

            query_embedding = await gemini.get_embedding(rewritten_query)
            rag_context = await supabase.search_knowledge_base(
                query_embedding=query_embedding,
                query_text=rewritten_query,
                instance_id=payload.instance_id,
                match_threshold=0.3,
                match_count=gemini.settings.rag_match_count,
            )

        if Route.checkout in routes and has_explicit_commercial_intent:
            checkout_products = [
                ProductCard(**product)
                for product in await supabase.get_checkout_products()
            ]
            product_context = _format_checkout_product_context(checkout_products)
            commercial_context = _join_non_empty(
                _sanitize_legacy_checkout_context(
                    tenant_settings.get("commercial_context", "")
                ),
                product_context,
            )
            if force_checkout_from_last_price:
                selected_product = _select_checkout_product(
                    products=checkout_products,
                    message=payload.message,
                    chat_history=effective_history,
                    client_facts=client_facts,
                    dialog_state=dialog_state,
                )
            else:
                selected_product = _select_checkout_product(
                    products=checkout_products,
                    message=payload.message,
                    chat_history=effective_history,
                    client_facts=client_facts,
                    dialog_state=dialog_state,
                )
            selected_product = _with_checkout_product_image(selected_product)

        if roleplay_demo_active:
            combined_answer = await gemini.answer_roleplay_with_demo_context_json(
                message=payload.message,
                chat_history=effective_history,
                topic=str(dialog_state.get("roleplay_demo_topic") or ""),
                demo_context=str(dialog_state.get(ROLEPLAY_CONTEXT_SUMMARY_KEY) or ""),
                no_file_fallback=bool(dialog_state.get(ROLEPLAY_NO_FILE_FALLBACK_KEY)),
            )
            combined_predicted_route = combined_answer.get("predicted_route")
            combined_json_valid = bool(combined_answer.get("json_valid"))
            answer = str(combined_answer.get("text_response") or "").strip()
            if not combined_json_valid or not answer:
                answer = await gemini.answer_roleplay_with_demo_context(
                    message=payload.message,
                    chat_history=effective_history,
                    topic=str(dialog_state.get("roleplay_demo_topic") or ""),
                    demo_context=str(dialog_state.get(ROLEPLAY_CONTEXT_SUMMARY_KEY) or ""),
                    no_file_fallback=bool(dialog_state.get(ROLEPLAY_NO_FILE_FALLBACK_KEY)),
                )
            elif combined_predicted_route == Route.exit_roleplay:
                router_requested_roleplay_exit = True
                roleplay_demo = {"active": False, "exit": True, "router_exit": True}
                _clear_roleplay_state(dialog_state)
                session_metadata[DIALOG_STATE_KEY] = dialog_state
                roleplay_demo_active = False
                routes = [Route.rag_required]
                answer = (
                    "Маску снял, вернулся в режим архитектора Plum Dev. "
                    "Теперь можем посчитать, как собрать такого ИИ-продавца под ваш продукт: "
                    "какие 2-3 действия он должен делать вместо менеджера?"
                )
        elif force_checkout_from_last_price and selected_product:
            answer = _build_create_cart_answer(selected_product)
        else:
            combined_answer = await gemini.answer_with_route_json(
                message=payload.message,
                chat_history=effective_history,
                rag_context=rag_context,
                commercial_context=commercial_context,
                memory_context=memory_context,
                response_instruction=response_instruction,
                system_prompt_addon=tenant_settings.get("system_prompt_addon", ""),
                final_system_prompt=tenant_settings.get("final_system_prompt", ""),
                router_system_prompt=tenant_settings.get("router_system_prompt", ""),
                client_facts=client_facts,
            )
            combined_predicted_route = combined_answer.get("predicted_route")
            combined_json_valid = bool(combined_answer.get("json_valid"))
            answer = str(combined_answer.get("text_response") or "").strip()
            if not combined_json_valid or not answer:
                answer = await _answer_with_rag_retry(
                    gemini=gemini,
                    message=payload.message,
                    effective_history=effective_history,
                    rag_context=rag_context,
                    commercial_context=commercial_context,
                    memory_context=memory_context,
                    response_instruction=response_instruction,
                    system_prompt_addon=tenant_settings.get("system_prompt_addon", ""),
                    final_system_prompt=tenant_settings.get("final_system_prompt", ""),
                    client_facts=client_facts,
                )
            elif (
                combined_predicted_route == Route.roleplay
                and not roleplay_demo.get("active")
                and _is_explicit_roleplay_command(payload.message)
            ):
                topic = _extract_roleplay_demo_topic(payload.message)
                roleplay_demo = {
                    "active": True,
                    "topic": topic,
                    "new_request": True,
                    "router_entry": True,
                }
                dialog_state["roleplay_demo_active"] = True
                if topic:
                    dialog_state["roleplay_demo_topic"] = topic
                session_metadata[DIALOG_STATE_KEY] = dialog_state
                roleplay_gate_response = await _handle_roleplay_context_gate(
                    gemini=gemini,
                    supabase=supabase,
                    payload=payload,
                    effective_history=effective_history,
                    session_metadata=session_metadata,
                    dialog_state=dialog_state,
                    roleplay_demo=roleplay_demo,
                )
                if roleplay_gate_response is not None:
                    return roleplay_gate_response
            elif combined_predicted_route == Route.exit_roleplay and (
                roleplay_demo.get("active") or dialog_state.get("roleplay_demo_active")
            ):
                router_requested_roleplay_exit = True
                roleplay_demo = {"active": False, "exit": True, "router_exit": True}
                _clear_roleplay_state(dialog_state)
                session_metadata[DIALOG_STATE_KEY] = dialog_state
                roleplay_demo_active = False
                routes = [Route.rag_required]
        roleplay_output_active = _is_roleplay_output_context(
            answer=answer,
            roleplay_demo_active=roleplay_demo_active,
            dialog_state=dialog_state,
        )
        # Skip all B2B commercial post-processors when in roleplay OR on the exact turn
        # roleplay exits. The exit turn's answer is already a bridge phrase back to Plum Dev;
        # running qualification/CTA appenders on it would corrupt it with $300 tags and
        # "В проект добавим: [user objection]" artifacts.
        skip_b2b_postprocessing = roleplay_output_active or router_requested_roleplay_exit
        contact_guard_answer = (
            None
            if skip_b2b_postprocessing
            else _checkout_contact_guard_answer(
                message=payload.message,
                chat_history=effective_history,
                answer=answer,
                client_facts=client_facts,
            )
        )
        contact_guard_triggered = contact_guard_answer is not None
        if contact_guard_triggered:
            answer = contact_guard_answer or answer
            has_checkout_close_intent = False
            selected_product = None
        if _is_which_option_better_question(payload.message) and not skip_b2b_postprocessing:
            answer = _repair_which_option_better_answer(answer, client_facts)
        if sales_stage == "stage_3_price" and not skip_b2b_postprocessing:
            answer = _repair_stage_3_price_answer(answer, dialog_state)
        if _should_collapse_acknowledgement_after_answer(
            message=payload.message,
            chat_history=effective_history,
            routes=routes,
            sales_stage=sales_stage,
            content_followup=content_followup,
            has_explicit_commercial_intent=has_explicit_commercial_intent,
        ) and not skip_b2b_postprocessing:
            answer = _build_acknowledgement_continuation_answer(
                client_facts=client_facts,
                dialog_state=dialog_state,
            )
        if roleplay_output_active:
            answer = _sanitize_roleplay_output(answer)
        elif not router_requested_roleplay_exit:
            # B2B post-processors only run when fully outside roleplay context
            answer = _cleanup_plum_cta_from_roleplay_answer(answer)
            answer = _remove_forbidden_traffic_question_after_milestone(
                answer,
                dialog_state,
            )
            answer = _repair_completed_function_qualification_answer(
                answer=answer,
                user_message=payload.message,
                dialog_state=dialog_state,
            )
            answer = _repair_forbidden_roleplay_gate_answer(
                answer,
                payload.message,
            )
            answer = _cleanup_contact_cta_after_phone_collected(
                answer=answer,
                user_message=payload.message,
                dialog_state=dialog_state,
                client_facts=client_facts,
            )
        answer = _sanitize_prompt_leakage_answer(answer)
        if not skip_b2b_postprocessing:
            answer = _ensure_sales_initiative_answer(
                answer=answer,
                user_message=payload.message,
                dialog_state=dialog_state,
            )
        if not skip_b2b_postprocessing and _phone_already_collected(
            payload.message,
            dialog_state,
            client_facts,
        ):
            answer = _final_contact_confirmation_answer()
        answer = _format_messenger_answer(answer)
        dialog_state = _update_dialog_state_after_answer(
            dialog_state=dialog_state,
            user_message=payload.message,
            answer=answer,
            sales_stage=sales_stage,
            content_followup=content_followup,
            selected_product=selected_product if has_checkout_close_intent else None,
        )
        session_metadata[DIALOG_STATE_KEY] = dialog_state
        await supabase.upsert_chat_session_metadata(
            instance_id=payload.instance_id,
            channel=payload.channel,
            chat_id=payload.chat_id,
            metadata=session_metadata,
        )
        checkout_payload = (
            {"action": "CREATE_CART"}
            if has_checkout_close_intent and selected_product
            else None
        )

        response = ChatResponse(
            route=primary_route,
            routes=routes,
            answer=answer,
            checkout=bool(has_checkout_close_intent and selected_product),
            product_id=selected_product.product_id if has_checkout_close_intent and selected_product else None,
            product=selected_product if has_checkout_close_intent else None,
            metadata={
                "rag_context_found": bool(rag_context),
                "rag_query_rewritten": rewritten_query,
                "commercial_context_used": bool(commercial_context),
                "dynamic_product_context_used": bool(checkout_products),
                "explicit_commercial_intent": has_explicit_commercial_intent,
                "checkout_close_intent": has_checkout_close_intent,
                "force_checkout_from_last_price": force_checkout_from_last_price,
                "sales_stage": sales_stage or None,
                "content_followup": content_followup,
                "checkout_payload": checkout_payload,
                "memory_context_used": bool(memory_context),
                "new_session": is_new_session,
                "reset_context": payload.reset_context,
                "server_history_used": bool(logged_history),
                "logged_history_messages": len(logged_history),
                "payload_history_messages": len(payload.chat_history),
                "effective_history_messages": len(effective_history),
                "client_facts": client_facts,
                "dialog_state": dialog_state,
                "roleplay_demo_active": roleplay_demo_active,
                "roleplay_exit_router": router_requested_roleplay_exit,
                "roleplay_awaiting_context_file": bool(dialog_state.get(ROLEPLAY_AWAITING_CONTEXT_KEY)),
                "roleplay_context_source": dialog_state.get(ROLEPLAY_CONTEXT_SOURCE_KEY),
                "roleplay_no_file_fallback": bool(dialog_state.get(ROLEPLAY_NO_FILE_FALLBACK_KEY)),
                "combined_json_valid": combined_json_valid,
                "combined_predicted_route": (
                    combined_predicted_route.value
                    if isinstance(combined_predicted_route, Route)
                    else None
                ),
                "checkout_contact_guard": contact_guard_triggered,
                "checkout_products": [
                    product.model_dump(exclude_none=True)
                    for product in checkout_products
                ],
                "tenant_found": bool(tenant_settings),
            },
        )

        await supabase.log_chat(
            channel=payload.channel,
            chat_id=payload.chat_id,
            instance_id=payload.instance_id,
            message=payload.message,
            ai_response=response.answer,
            routes=response.routes,
            metadata=_build_log_metadata(response),
        )

        if _should_refresh_memory(payload, gemini, is_new_session):
            background_tasks.add_task(
                refresh_b2b_memory,
                gemini=gemini,
                supabase=supabase,
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                memory_summary_system_prompt=tenant_settings.get(
                    "memory_summary_system_prompt",
                    "",
                ),
            )

        return response

    except HTTPException:
        raise
    except Exception as exc:
        if _is_quota_or_rate_limit_error(exc):
            logger.warning(
                "AI provider quota/rate limit reached while processing chat request"
            )
            if not _generation_fallback_enabled():
                return ChatResponse(
                    route=Route.general,
                    routes=[Route.general],
                    answer=_format_messenger_answer(_build_generation_error_answer(exc)),
                    metadata={
                        "provider_quota_limited": True,
                        "fallback_answer": False,
                        "generation_failed": True,
                        "generation_error": _exception_chain_text(exc),
                        "tenant_found": False,
                    },
                )
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=_format_messenger_answer(_build_generation_fallback_answer(payload)),
                metadata={
                    "provider_quota_limited": True,
                    "fallback_answer": True,
                    "tenant_found": False,
                },
            )

        logger.exception("Failed to process chat request")
        if not _generation_fallback_enabled():
            return ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=_format_messenger_answer(_build_generation_error_answer(exc)),
                metadata={
                    "generation_failed": True,
                    "fallback_answer": False,
                    "generation_error": _exception_chain_text(exc),
                    "tenant_found": False,
                },
            )
        return ChatResponse(
            route=Route.general,
            routes=[Route.general],
            answer=_format_messenger_answer(_build_generation_fallback_answer(payload)),
            metadata={
                "generation_failed": True,
                "fallback_answer": True,
                "tenant_found": False,
            },
        )


async def _answer_with_rag_retry(
    *,
    gemini: GeminiService,
    message: str,
    effective_history: list[ChatHistoryMessage],
    rag_context: str,
    commercial_context: str,
    memory_context: str,
    response_instruction: str,
    system_prompt_addon: str,
    final_system_prompt: str,
    client_facts: dict[str, object] | None = None,
) -> str:
    last_exc: Exception | None = None
    clean_history = _strip_generation_fallback_history(effective_history)
    attempts = (
        {
            "history": effective_history,
            "rag_context": rag_context,
            "memory_context": memory_context,
            "label": "normal",
        },
        {
            "history": clean_history,
            "rag_context": rag_context,
            "memory_context": memory_context,
            "label": "clean-history",
        },
        {
            "history": clean_history,
            "rag_context": "",
            "memory_context": "",
            "label": "clean-history-no-rag",
        },
    )
    for attempt, attempt_config in enumerate(attempts, start=1):
        try:
            answer = await gemini.answer_with_rag(
                message,
                attempt_config["history"],
                rag_context=attempt_config["rag_context"],
                commercial_context=commercial_context,
                memory_context=attempt_config["memory_context"],
                response_instruction=response_instruction,
                system_prompt_addon=system_prompt_addon,
                final_system_prompt=final_system_prompt,
                client_facts=client_facts,
            )
            normalized_answer = answer.strip()
            if normalized_answer:
                return normalized_answer
            raise RuntimeError("Gemini returned an empty final answer")
        except Exception as exc:
            last_exc = exc
            if attempt >= len(attempts):
                break
            logger.warning(
                "AI answer generation failed on %s attempt %s; retrying with cleaned state: %s",
                attempt_config["label"],
                attempt,
                exc,
            )
            await asyncio.sleep(0.5)

    raise RuntimeError("AI answer generation failed after retry") from last_exc


def _generation_fallback_enabled() -> bool:
    return os.getenv("ENABLE_GENERATION_FALLBACK", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _exception_chain_text(exc: Exception) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(parts) < 4:
        text = str(current).strip()
        if text:
            parts.append(text)
        current = current.__cause__ or current.__context__
    return " | ".join(parts)


def _build_generation_error_answer(exc: Exception) -> str:
    text = _exception_chain_text(exc).lower()
    if "429" in text or "quota" in text or "resource_exhausted" in text:
        return (
            "ИИ сейчас не ответил: Google вернул лимит/квоту по API-ключу. "
            "Проверьте billing/quota для проекта этого GEMINI_API_KEY."
        )
    return "ИИ сейчас не ответил. Подробная причина записана в логах микросервиса."


def _build_generation_fallback_answer(payload: ChatRequest) -> str:
    full_context = " ".join(
        [
            payload.message,
            *[item.content for item in payload.chat_history],
        ]
    ).casefold().replace("ё", "е")

    if _is_ai_agent_intro_question(payload.message, full_context):
        return (
            "ИИ-агент — это помощник в переписке, который отвечает клиентам, квалифицирует заявки "
            "и передает горячие лиды в CRM или менеджеру."
        )

    if _is_ai_agent_mechanism_question(payload.message, full_context):
        return (
            "Схема простая: агент получает вопрос клиента, сверяется с базой знаний, уточняет нужные данные "
            "и передает заявку в CRM, таблицу или авто-корзину."
        )

    if _is_ai_project_timeline_question(payload.message, full_context):
        return (
            "Срок зависит от каналов, базы знаний и интеграций. Простой ассистент можно оценить быстро, "
            "а агент с CRM и авто-корзиной лучше считать по вашей воронке.\n\n"
            "Напишите нишу и основной канал заявок: Instagram, WhatsApp, Telegram или сайт."
        )

    if _is_affirmative_after_fallback_offer(payload.message, payload.chat_history):
        return "Напишите нишу, основной канал заявок и телефон для связи — соберу первичный расчет проекта."

    if _is_document_request(payload.message):
        return DOCUMENTS_SITE_ANSWER

    if _has_explicit_commercial_intent(payload.message, payload.chat_history):
        return (
            "Я делаю авто-корзины, ИИ-агентов и умные воронки под ключ. "
            "Чтобы посчитать без выдуманных цифр, нужны ниша, канал заявок и что именно хотите автоматизировать."
        )

    return (
        "Я помогаю бизнесу внедрять ИИ-агентов, базы знаний, CRM-интеграции и авто-корзины под ключ. "
        "Подскажите, основной поток клиентов сейчас идет из Instagram или сразу в WhatsApp?"
    )


def _is_ai_agent_intro_question(message: str, full_context: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    asks_definition = bool(
        re.search(r"\bчто\s+(?:это|такое)\b", normalized)
        or re.search(r"\bрасскажи(?:те)?\b", normalized)
        or re.search(r"\bобъясни(?:те)?\b", normalized)
    )
    mentions_ai_agent = bool(
        re.search(r"ии-?агент|ai\s+agent|агент|бот|чатбот|автоматизац", full_context)
    )
    return asks_definition and mentions_ai_agent


def _is_ai_agent_mechanism_question(message: str, full_context: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    asks_mechanism = bool(
        re.search(r"\bкак\s+(?:он|это|агент|бот)?\s*работ", normalized)
        or re.search(r"\bза\s+счет\s+чего\b", normalized)
        or re.search(r"\bмеханизм\b", normalized)
        or re.search(r"\bчто\s+делает\b", normalized)
    )
    mentions_ai_agent = bool(
        re.search(r"ии-?агент|ai\s+agent|агент|бот|чатбот|база\s+знаний|crm|срм|авто-?корзин", full_context)
    )
    return asks_mechanism and mentions_ai_agent


def _is_ai_project_timeline_question(message: str, full_context: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    asks_timing = bool(
        re.search(r"\bкак\s+быстро\b", normalized)
        or re.search(r"\bза\s+сколько\b", normalized)
        or re.search(r"\bкогда\b", normalized)
        or re.search(r"\bсрок", normalized)
        or re.search(r"\bсколько\s+(?:делать|внедрять|запускать)", normalized)
    )
    project_context = bool(
        re.search(r"агент|бот|crm|срм|интеграц|воронк|автоматизац|авто-?корзин", normalized)
        or re.search(r"агент|бот|crm|срм|интеграц|воронк|автоматизац|авто-?корзин", full_context)
    )
    return asks_timing and project_context


def _infer_sales_stage_transition_local(
    *,
    message: str,
    chat_history: list[ChatHistoryMessage],
    client_facts: dict[str, object],
    dialog_state: dict[str, object],
) -> dict[str, object]:
    normalized = message.casefold().replace("ё", "е")
    last_assistant = _last_assistant_message(chat_history).casefold().replace("ё", "е")
    stage = "none"
    commercial_intent = False
    checkout_intent = False

    if _is_explicit_plum_price_request(message):
        stage = "stage_3_price"
        commercial_intent = True
    elif _contains_close_consent_signal(message) or (
        _is_affirmative_short_reply(normalized)
        and re.search(r"посчитать|расчет|рассчитать|собрать\s+спецификац|начнем\s+с", last_assistant)
    ):
        stage = "stage_3_price"
        commercial_intent = True
    elif _has_explicit_commercial_intent(message, None):
        stage = "stage_3_price"
        commercial_intent = True
    elif _is_affirmative_short_reply(normalized) and re.search(
        r"вариант|пакет|сравн|показать|объяснить|разложить",
        last_assistant,
    ):
        stage = "stage_2_comparison"
        commercial_intent = True

    if (
        _is_affirmative_short_reply(normalized)
        and dialog_state.get("price_exposed")
        and re.search(r"оформ|заявк|перейти|запуск|беру|подходит", normalized)
    ):
        stage = "stage_4_checkout"
        commercial_intent = True
        checkout_intent = True

    return {
        "stage": stage,
        "commercial_intent": commercial_intent,
        "checkout_intent": checkout_intent,
    }


def _infer_content_followup_local(
    *,
    message: str,
    chat_history: list[ChatHistoryMessage],
) -> str:
    previous_assistant = _last_assistant_message(chat_history)
    if "?" not in previous_assistant:
        return "none"

    full_context = f"{previous_assistant}\n{message}".casefold().replace("ё", "е")
    normalized = message.casefold().replace("ё", "е")
    if _is_ai_agent_mechanism_question(message, full_context) or (
        _is_affirmative_short_reply(normalized)
        and re.search(r"как\s+(?:это|он|агент|бот)\s+работ|механизм|за\s+счет\s+чего", previous_assistant.casefold().replace("ё", "е"))
    ):
        return "mechanism_detail"
    if (
        re.search(r"безопасн|надежн|качество|ошиб|контрол|доступ\s+к\s+данным", normalized)
        or (
            _is_affirmative_short_reply(normalized)
            and re.search(r"безопасн|надежн|качество|ошиб|контрол", previous_assistant.casefold().replace("ё", "е"))
        )
    ):
        return "safety_quality_detail"
    return "none"


def _is_affirmative_after_fallback_offer(
    message: str,
    chat_history: list[ChatHistoryMessage],
) -> bool:
    if not _is_affirmative_short_reply(message.casefold()):
        return False

    last_assistant = _last_assistant_message(chat_history).casefold().replace("ё", "е")
    return any(
        marker in last_assistant
        for marker in (
            "соберу первичный расчет",
            "начнем расчет",
            "посчитать проект",
            "основной поток клиентов",
        )
    )


def _is_document_request(message: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    return any(re.search(pattern, normalized) for pattern in DOCUMENT_REQUEST_PATTERNS)


def _is_plain_greeting(message: str) -> bool:
    normalized = re.sub(r"[^\w\sа-яА-ЯёЁ-]", " ", message.casefold().replace("ё", "е"))
    normalized = " ".join(normalized.split())
    return normalized in {
        "привет",
        "здравствуйте",
        "добрый день",
        "доброе утро",
        "добрый вечер",
        "hello",
        "hi",
        "start",
        "reset",
    }


def _is_affirmative_short_reply(normalized_message: str) -> bool:
    normalized = re.sub(r"[^\w\sа-яА-ЯёЁ-]", " ", normalized_message)
    normalized = " ".join(normalized.split())
    if not normalized:
        return False

    affirmative_phrases = {
        "да",
        "давай",
        "давайте",
        "ок",
        "окей",
        "хорошо",
        "хочу",
        "жду",
        "согласен",
        "согласна",
        "подходит",
        "пойдет",
        "пойдёт",
        "можно",
        "беру",
        "возьму",
        "оформляем",
        "оформляйте",
        "оформите",
        "оформить",
        "го",
        "yes",
        "yep",
        "ok",
    }
    return normalized in affirmative_phrases


def _is_all_functions_answer(message: str) -> bool:
    normalized = re.sub(r"[^\w\sа-яА-ЯёЁ-]", " ", message.casefold().replace("ё", "е"))
    normalized = " ".join(normalized.split())
    exact_match = normalized in {
        "все",
        "все вместе",
        "все функции",
        "все задачи",
        "сразу все",
        "хочу все",
        "хочу все вместе",
        "хочу сразу все",
        "нужно все",
        "нужно все вместе",
        "каждая",
        "каждую",
        "каждое",
        "каждый",
        "любые",
        "любая",
        "любой",
        "любую",
        "полностью",
        "под ключ",
    }
    if exact_match:
        return True
    return bool(
        re.search(r"\b(?:хочу|нужно|надо|сделать|автоматизировать|внедрить)?\s*(?:сразу\s+)?все\s+(?:вместе|функц|задач|процесс|под\s+ключ)\b", normalized)
        or re.search(r"\b(?:комплексн\w+|под\s+ключ|полная\s+автоматизац|автоматизировать\s+все)\b", normalized)
    )


def _is_nonempty_qualification_answer(message: str) -> bool:
    normalized = re.sub(r"[^\w\sа-яА-ЯёЁ-]", " ", message.casefold().replace("ё", "е"))
    normalized = " ".join(normalized.split())
    return bool(normalized)


def _latest_assistant_asked_agent_tasks(chat_history: list[ChatHistoryMessage]) -> bool:
    previous = _last_assistant_message(chat_history).casefold().replace("ё", "е")
    return bool(
        re.search(r"какие\s+.*(?:задач|функц|действ)", previous)
        or re.search(r"что\s+из\s+этого\s+.*(?:важн|главн)", previous)
        or re.search(r"какие\s+2-3\s+действ", previous)
        or re.search(r"что\s+(?:вы\s+)?хотите\s+автоматиз", previous)
        or re.search(r"(?:задач|функц|действ).{0,80}(?:ии-?агент|бот|ассистент)", previous)
    )


def _is_explicit_plum_price_request(message: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    price_marker = bool(
        re.search(r"\bсколько\s+(?:будет\s+)?(?:стоить|стоит|имплементир|внедр|сделать|собрать)", normalized)
        or re.search(r"\b(?:цена|стоимость|прайс|бюджет|смета)\b", normalized)
        or re.search(r"\bкакой\s+бюджет\b", normalized)
    )
    project_marker = bool(
        re.search(r"ии|ai|агент|бот|автоматизац|имплемент|внедр|сделать|собрать|все\s+вместе|под\s+ключ", normalized)
    )
    return price_marker and project_marker


def _strip_generation_fallback_history(
    history: list[ChatHistoryMessage],
) -> list[ChatHistoryMessage]:
    return [
        item
        for item in history
        if not (item.role == "assistant" and _is_generation_fallback_text(item.content))
    ]


def _is_generation_fallback_text(text: str) -> bool:
    return any(marker in text for marker in GENERATION_FALLBACK_MARKERS)


async def refresh_b2b_memory(
    *,
    gemini: GeminiService,
    supabase: SupabaseService,
    instance_id: str,
    channel: str,
    chat_id: str,
    memory_summary_system_prompt: str = "",
) -> None:
    try:
        dialog = await supabase.fetch_session_dialog(
            instance_id=instance_id,
            channel=channel,
            chat_id=chat_id,
        )
        if not dialog:
            return
        message_count = _session_dialog_message_count(dialog)
        if message_count < gemini.settings.summary_after_messages:
            return
        if (
            message_count > gemini.settings.summary_after_messages
            and message_count % 8 != 0
        ):
            return

        existing_summary = await supabase.get_user_memory(
            instance_id=instance_id,
            channel=channel,
            chat_id=chat_id,
        )
        summary = await gemini.summarize_b2b_memory(
            dialog,
            existing_summary=existing_summary,
            system_prompt=memory_summary_system_prompt,
        )
        await supabase.upsert_user_memory(
            instance_id=instance_id,
            channel=channel,
            chat_id=chat_id,
            summary=summary,
        )
    except Exception as exc:
        error_text = str(exc)
        if "RESOURCE_EXHAUSTED" in error_text or "429" in error_text:
            logger.warning(
                "Skipped B2B memory refresh because Gemini quota/rate limit was reached"
            )
            return

        logger.exception("Failed to refresh B2B memory")


def _session_dialog_message_count(dialog: str) -> int:
    return dialog.count("\nUser:") + dialog.count("\nAssistant:")


def _join_non_empty(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _sanitize_legacy_checkout_context(text: str) -> str:
    normalized_text = (text or "").strip()
    if not normalized_text:
        return ""

    legacy_patterns = (
        r"42\s*000",
        r"49\s*500",
        r"ФИО",
        r"номер\s+телефон",
        r"delivery\s+legacy",
        r"full\s+name",
        r"delivery\s+(?:city|address)",
    )
    lines: list[str] = []
    for line in normalized_text.splitlines():
        normalized_line = line.strip().casefold()
        if any(re.search(pattern, normalized_line) for pattern in legacy_patterns):
            continue
        lines.append(line)

    return "\n".join(lines).strip()


def _format_checkout_product_context(products: list[ProductCard]) -> str:
    if not products:
        return (
            "Dynamic product context:\n"
            "No checkout products were provided. Do not name any product price."
        )

    lines = [
        "Dynamic product context:",
        "Используй только цены и условия, которые переданы в динамическом контексте услуг. Не выдумывай стоимость.",
        "Available checkout products:",
    ]
    for product in products:
        dosage = f", dosage={product.dosage}" if product.dosage else ""
        price = (
            f", price={product.price_tenge} ₸"
            if product.price_tenge is not None
            else ", price=unknown"
        )
        lines.append(
            f"- product_id={product.product_id}, title={product.title}{dosage}{price}"
        )

    return "\n".join(lines)


def _format_content_followup_instruction(content_followup: str) -> str:
    if content_followup == "mechanism_detail":
        return (
            "Content follow-up: MECHANISM DETAIL.\n"
            "The user agreed to learn more. It is categorically forbidden to repeat generic phrases about AI magic. "
            "Write 2-4 short sentences. Explain the practical flow: user message, knowledge base, qualification, CRM/table handoff, and optional smart cart. "
            "Avoid technical overload. This answer must only expand architecture/mechanism. Do not ask any new question and do not mention price, package selection, cart, or checkout."
        )
    if content_followup == "safety_quality_detail":
        return (
            "Content follow-up: SAFETY AND QUALITY DETAIL.\n"
            "The user agreed to learn more about reliability/security/quality. Explain data access, logging, handoff control, testing, and support process in simple Russian. "
            "Do not repeat the previous short answer. Do not promise absolute security or flawless operation. "
            "This answer must only expand reliability/quality. Do not ask any new question and do not mention price, package selection, cart, or checkout."
        )
    return ""


def _format_dialog_state_instruction(
    *,
    message: str,
    client_facts: dict[str, object],
    dialog_state: dict[str, object],
    sales_stage: str,
    content_followup: str,
) -> str:
    instructions: list[str] = []
    business_sphere = str(client_facts.get("business_sphere") or "").strip()
    lead_channel = str(client_facts.get("lead_channel") or "").strip()
    automation_goal = str(client_facts.get("automation_goal") or dialog_state.get("automation_goal") or "").strip()
    automation_goal_text = str(dialog_state.get("automation_goal_text") or "").strip()

    last_offer_type = str(dialog_state.get("last_offer_type") or "")
    if dialog_state.get("all_agent_functions_selected") or automation_goal == "all_sales_agent_functions":
        instructions.append(
            "Dialog state: the user answered broadly ('все/каждая/любые') to the agent task selection question. "
            "Accept it as a valid final answer: all agent functions are selected. "
            "It is strictly forbidden to ask again which tasks/functions are most important. "
            "Say: 'Отличный подход, комплексная автоматизация дает максимальный эффект.' "
            "Move forward to project specification calculation, price orientation, or the next concrete implementation step."
        )
    elif dialog_state.get("qualification_tasks_completed") or automation_goal == "custom_agent_functions":
        instructions.append(
            "Dialog state: the user already answered the bot/AI-agent function qualification question. "
            f"Captured task wording: {automation_goal_text or 'the user gave a free-form/vague answer'}. "
            "Treat this qualification step as completed. It is strictly forbidden to ask again what the bot should automate, which 2-3 actions it should do, or what is most important. "
            "Confirm the captured task and move forward to project specification calculation or price orientation in the same message."
        )
    if (
        business_sphere
        and lead_channel
        and not automation_goal
        and sales_stage == "none"
        and last_offer_type not in {"price_calculation", "price_presentation", "checkout"}
    ):
        instructions.append(
            "Dialog state: business sphere and lead channel are known, but the automation goal is still unclear. "
            "Do not calculate price yet. Ask only which part of the funnel should be automated first."
        )

    focus = str(dialog_state.get("last_offer_product") or dialog_state.get("current_product_focus") or "").strip()
    if focus in VALID_SERVICE_FOCUS:
        instructions.append(
            f"Dialog state: current local service focus is {focus}. "
            "If the user is asking about timeline or agreeing to a calculation around this focus, keep this package unless the user explicitly asks to compare or change it."
        )

    if dialog_state.get("mechanism_explained") and content_followup != "mechanism_detail":
        instructions.append(
            "Dialog state: the mechanism has already been explained. Do not offer to explain how it works again. If the user complains that it was already explained, acknowledge it and move to the next useful commercial step without repeating the mechanism."
        )

    if dialog_state.get("safety_answered") and content_followup != "safety_quality_detail":
        instructions.append(
            "Dialog state: reliability/security/quality has already been answered. Do not offer the same explanation again unless the user asks a new question."
        )

    if sales_stage == "stage_3_price" and focus in VALID_SERVICE_FOCUS:
        instructions.append(
            f"Dialog state: the user agreed to a project calculation for service focus {focus}. Present that focused estimate first if dynamic context contains it."
        )

    if _is_which_option_better_question(message):
        instructions.append(
            "Dialog state: the user is comparing which AI solution is better. Give a direct recommendation with one short reason. "
            "Do not repeat the same closing question from the previous assistant message. Do not push checkout in this answer unless the user clearly chooses a package."
        )

    return "\n".join(instructions)


def _build_dialog_state_for_request(
    *,
    session_metadata: dict[str, Any],
    chat_history: list[ChatHistoryMessage],
    message: str,
    client_facts: dict[str, object],
) -> dict[str, object]:
    stored_state = session_metadata.get(DIALOG_STATE_KEY) or {}
    if not isinstance(stored_state, dict):
        stored_state = {}

    state: dict[str, object] = {
        key: value
        for key, value in stored_state.items()
        if value not in (None, "")
    }
    state.setdefault("asked_offers", [])

    inferred = _infer_dialog_state_from_history(chat_history, client_facts)
    for key, value in inferred.items():
        if value not in (None, "", []):
            state[key] = value

    previous_assistant = _last_assistant_message(chat_history)
    if previous_assistant:
        state["last_assistant_had_question"] = "?" in previous_assistant
        offer = _infer_offer_from_assistant(previous_assistant)
        if offer:
            state.update(offer)

    current_focus = _extract_service_focus(message)
    if current_focus:
        state["current_product_focus"] = current_focus
    if _latest_assistant_asked_agent_tasks(chat_history) and _is_nonempty_qualification_answer(message):
        if _is_all_functions_answer(message):
            state["automation_goal"] = "all_sales_agent_functions"
            state["all_agent_functions_selected"] = True
            state["price_exposed"] = True
            state["close_consented"] = True
        else:
            state["automation_goal"] = "custom_agent_functions"
            state["automation_goal_text"] = message.strip()[:240]
        state["qualification_tasks_completed"] = True
        state["last_offer_type"] = "price_calculation"
        state["last_offer_product"] = "agent"
    phone = _extract_phone_digits(message) or str(client_facts.get("contact_phone") or "").strip()
    if phone:
        state["contact_phone"] = phone
        state["contact_phone_collected"] = True
        state["close_consented"] = True

    recommended = _recommended_service_from_facts(client_facts)
    if recommended:
        state["recommendation_product"] = recommended
    elif "recommendation_product" not in state:
        state["recommendation_product"] = "base"

    return _normalize_dialog_state(state)


def _infer_dialog_state_from_history(
    chat_history: list[ChatHistoryMessage],
    client_facts: dict[str, object],
) -> dict[str, object]:
    state: dict[str, object] = {}
    asked_offers: list[str] = []

    for item in chat_history:
        text = item.content
        normalized = text.casefold().replace("ё", "е")
        if item.role == "user":
            if _contains_sales_pain_signal(text):
                state["pain_expressed"] = True
            if _contains_close_consent_signal(text):
                state["close_consented"] = True
        if item.role == "assistant":
            focus = _extract_service_focus(text)
            if focus:
                state["current_product_focus"] = focus
            offer = _infer_offer_from_assistant(text)
            if offer:
                state.update(offer)
                offer_key = str(offer.get("last_offer_type") or "")
                offer_product = str(offer.get("last_offer_product") or "")
                offer_basis = str(offer.get("last_offer_basis") or "")
                if offer_key:
                    parts = [offer_key]
                    if offer_product:
                        parts.append(offer_product)
                    if offer_basis:
                        parts.append(offer_basis)
                    asked_offers.append(":".join(parts))
            if _assistant_explained_mechanism(normalized):
                state["mechanism_explained"] = True
            if _assistant_answered_safety(normalized):
                state["safety_answered"] = True
            if re.search(r"базов\w*\s+ассистент|ассистент", normalized) and _contains_price_signal(normalized):
                state["price_base_presented"] = True
            if re.search(r"авто-?корзин|корзин", normalized) and _contains_price_signal(normalized):
                state["price_cart_presented"] = True
            if re.search(r"ии-?агент|агент|интеграц|crm|срм", normalized) and _contains_price_signal(normalized):
                state["price_agent_presented"] = True
            if _contains_price_signal(normalized):
                state["price_exposed"] = True
            if re.search(r"режим\s+тест-драйва|маск[ау]\s+.*менеджер|/roleplay", normalized):
                state["demo_activated"] = True

    recommendation = _recommended_service_from_facts(client_facts)
    if recommendation:
        state["recommendation_product"] = recommendation
    if asked_offers:
        state["asked_offers"] = asked_offers[-12:]
    return state


def _normalize_dialog_state(state: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    dosage_fields = {
        "current_product_focus",
        "recommendation_product",
        "last_offer_product",
        "selected_checkout_product",
    }
    for key, value in state.items():
        if key in dosage_fields:
            focus = _normalize_service_focus_value(value)
            if focus:
                normalized[key] = focus
            continue
        if key in {
            "mechanism_explained",
            "safety_answered",
            "price_base_presented",
            "price_cart_presented",
            "price_agent_presented",
            "last_assistant_had_question",
            "roleplay_demo_active",
            "all_agent_functions_selected",
            "qualification_tasks_completed",
            ROLEPLAY_AWAITING_CONTEXT_KEY,
            ROLEPLAY_NO_FILE_FALLBACK_KEY,
            *BUYING_MILESTONE_KEYS,
        }:
            normalized[key] = bool(value)
            continue
        if key == ROLEPLAY_CONTEXT_WAIT_COUNT_KEY:
            count = _coerce_int(value)
            if count is not None:
                normalized[key] = count
            continue
        if key == ROLEPLAY_CONTEXT_SUMMARY_KEY:
            text = str(value).strip()
            if text:
                normalized[key] = text[:5000]
            continue
        if key in {"roleplay_demo_topic", ROLEPLAY_CONTEXT_SOURCE_KEY}:
            text = str(value).strip()
            if text:
                normalized[key] = text[:240 if key == ROLEPLAY_CONTEXT_SOURCE_KEY else 80]
            continue
        if key == "asked_offers":
            if isinstance(value, list):
                normalized[key] = [str(item)[:80] for item in value if str(item).strip()][-12:]
            continue
        if key in {"last_offer_type", "last_offer_basis", "automation_goal", "automation_goal_text"}:
            text = str(value).strip()
            if text:
                normalized[key] = text[:240 if key == "automation_goal_text" else 80]
    return normalized


def _apply_dialog_state_stage_override(
    *,
    sales_stage: str,
    dialog_state: dict[str, object],
    message: str,
) -> str:
    if not _is_affirmative_short_reply(message.casefold()):
        return sales_stage
    last_offer_type = str(dialog_state.get("last_offer_type") or "")
    last_offer_product = str(dialog_state.get("last_offer_product") or "")
    if (
        last_offer_type in {"price_calculation", "price_presentation"}
        and sales_stage in {"none", "stage_2_comparison", "stage_3_price"}
    ):
        return "stage_3_price"
    if (
        last_offer_type == "checkout"
        and last_offer_product in VALID_SERVICE_FOCUS
        and sales_stage in {"none", "stage_3_price", "stage_4_checkout"}
    ):
        return "stage_4_checkout"
    if (
        last_offer_type == "comparison"
        and last_offer_product in VALID_SERVICE_FOCUS
        and (
            dialog_state.get(f"price_{last_offer_product}_presented")
            or dialog_state.get("price_base_presented")
            or dialog_state.get("price_cart_presented")
            or dialog_state.get("price_agent_presented")
        )
        and sales_stage in {"none", "stage_3_price", "stage_4_checkout"}
    ):
        return "stage_4_checkout"
    return sales_stage


def _apply_product_selection_stage_override(
    *,
    sales_stage: str,
    dialog_state: dict[str, object],
    message: str,
) -> str:
    selected_focus = _extract_service_focus(message)
    if selected_focus not in VALID_SERVICE_FOCUS:
        return sales_stage
    price_presented = bool(
        dialog_state.get(f"price_{selected_focus}_presented")
        or dialog_state.get("price_base_presented")
        or dialog_state.get("price_cart_presented")
        or dialog_state.get("price_agent_presented")
    )
    if price_presented and sales_stage in {"none", "stage_2_comparison", "stage_3_price", "stage_4_checkout"}:
        dialog_state["current_product_focus"] = selected_focus
        dialog_state["last_offer_product"] = selected_focus
        return "stage_4_checkout"
    return sales_stage


def _should_block_commercial_until_goal(
    *,
    message: str,
    client_facts: dict[str, object],
    dialog_state: dict[str, object],
    sales_stage: str,
) -> bool:
    if sales_stage not in {"stage_2_comparison", "stage_3_price", "stage_4_checkout"}:
        return False
    last_offer_type = str(dialog_state.get("last_offer_type") or "")
    last_offer_product = str(dialog_state.get("last_offer_product") or "")
    if last_offer_type in {"price_calculation", "price_presentation", "checkout"}:
        return False
    if _has_explicit_commercial_intent(message, None):
        return False
    business_sphere = str(client_facts.get("business_sphere") or "").strip()
    lead_channel = str(client_facts.get("lead_channel") or "").strip()
    automation_goal = str(client_facts.get("automation_goal") or dialog_state.get("automation_goal") or "").strip()
    return bool(business_sphere and lead_channel and not automation_goal)


def _update_dialog_state_after_answer(
    *,
    dialog_state: dict[str, object],
    user_message: str,
    answer: str,
    sales_stage: str,
    content_followup: str,
    selected_product: ProductCard | None,
) -> dict[str, object]:
    state = dict(dialog_state)
    phone = _extract_phone_digits(user_message)
    if phone:
        state["contact_phone"] = phone
        state["contact_phone_collected"] = True
        state["close_consented"] = True
    user_focus = _extract_service_focus(user_message)
    answer_focus = _extract_service_focus(answer)
    if user_focus:
        state["current_product_focus"] = user_focus
    elif answer_focus:
        state["current_product_focus"] = answer_focus

    if content_followup == "mechanism_detail" or _assistant_explained_mechanism(answer):
        state["mechanism_explained"] = True
    if content_followup == "safety_quality_detail" or _assistant_answered_safety(answer):
        state["safety_answered"] = True

    normalized_answer = answer.casefold().replace("ё", "е")
    if re.search(r"базов\w*\s+ассистент|ассистент", normalized_answer) and _contains_price_signal(normalized_answer):
        state["price_base_presented"] = True
    if re.search(r"авто-?корзин|корзин", normalized_answer) and _contains_price_signal(normalized_answer):
        state["price_cart_presented"] = True
    if re.search(r"ии-?агент|агент|интеграц|crm|срм", normalized_answer) and _contains_price_signal(normalized_answer):
        state["price_agent_presented"] = True

    offer = _infer_offer_from_assistant(answer)
    if offer:
        state.update(offer)
        asked = state.get("asked_offers")
        asked_offers = list(asked) if isinstance(asked, list) else []
        offer_key = str(offer.get("last_offer_type") or "")
        offer_product = str(offer.get("last_offer_product") or "")
        offer_basis = str(offer.get("last_offer_basis") or "")
        if offer_key:
            parts = [offer_key]
            if offer_product:
                parts.append(offer_product)
            if offer_basis:
                parts.append(offer_basis)
            asked_offers.append(":".join(parts))
            state["asked_offers"] = asked_offers[-12:]
    elif "?" not in answer:
        state.pop("last_offer_type", None)
        state.pop("last_offer_product", None)
        state.pop("last_offer_basis", None)

    if selected_product:
        selected_focus = _checkout_product_service_focus(selected_product)
        if selected_focus:
            state["selected_checkout_product"] = selected_focus

    _apply_buying_milestones(
        state,
        user_message=user_message,
        answer=answer,
        roleplay_active=bool(dialog_state.get("roleplay_demo_active")),
    )

    return _normalize_dialog_state(state)


def _infer_offer_from_assistant(text: str) -> dict[str, object]:
    normalized = text.casefold().replace("ё", "е")
    if "?" not in normalized:
        return {}

    product = _extract_service_focus(text)
    if product and re.search(r"начнем|начать|бер[её]м|подходит|оформ|запускаем|внедряем", normalized):
        return {
            "last_offer_type": "checkout",
            "last_offer_product": product,
        }
    if re.search(r"стоимост|цен[ауые]|прайс|рассчита", normalized):
        return {
            "last_offer_type": "price_calculation",
            "last_offer_product": product or "",
            "last_offer_basis": "service_options" if _assistant_offered_both_options(normalized) else "",
        }
    if re.search(r"вариант|сравн|пакет|ассистент|авто-?корзин|агент", normalized):
        return {
            "last_offer_type": "comparison",
            "last_offer_product": product or "",
        }
    if re.search(r"оформ|заказ|купить|перейти|корзин|созвон|заявк|внедр", normalized):
        return {
            "last_offer_type": "checkout",
            "last_offer_product": product or "",
        }
    if re.search(r"как.*работ|механизм|подробнее", normalized):
        return {
            "last_offer_type": "mechanism_detail",
            "last_offer_product": product or "",
        }
    if re.search(r"безопас|качество|надежн|доступ|данн|логир|поддерж", normalized):
        return {
            "last_offer_type": "safety_quality_detail",
            "last_offer_product": product or "",
        }
    return {}


def _assistant_offered_both_options(normalized_text: str) -> bool:
    return bool(
        re.search(r"оба|обоим|несколько|дв[ауе]\s+вариант|пакет", normalized_text)
        or re.search(r"ассистент", normalized_text) and re.search(r"агент|авто-?корзин", normalized_text)
    )


def _contains_price_signal(normalized_text: str) -> bool:
    return bool(
        re.search(r"(?:\$|₸|тг|тенге|usd|kzt)", normalized_text)
        or re.search(r"сколько\s+(?:будет\s+)?(?:стоить|стоит|имплементир|внедр|сделать|собрать)", normalized_text)
        or re.search(r"\b(?:цена|стоимость|прайс|бюджет|смета)\b", normalized_text)
        or re.search(r"(?:цена|стоимост|прайс|смет|бюджет).{0,40}\d", normalized_text)
        or re.search(r"\d[\d\s]{2,}.{0,20}(?:тенге|тг|₸|usd|доллар)", normalized_text)
    )


def _contains_sales_pain_signal(text: str) -> bool:
    normalized = text.casefold().replace("ё", "е")
    return bool(
        re.search(
            r"менеджер.{0,40}(туп|плох|слаб|не\s+уме|слив|долго|медлен|не\s+закры|не\s+дожим)",
            normalized,
        )
        or re.search(r"лид.{0,40}(слив|теря|не\s+закрыв|не\s+дожим|молчат|уход)", normalized)
        or re.search(r"клиент.{0,40}(уход|молчат|слив|теря|не\s+покуп)", normalized)
        or re.search(r"долго\s+отвеч|не\s+успева|плохо\s+закрыв|нет\s+дожим", normalized)
    )


def _contains_close_consent_signal(text: str) -> bool:
    normalized = text.casefold().replace("ё", "е")
    return bool(
        re.search(r"\b(давай|давайте|хочу|готов|погнали|начинаем|запускаем|считай|посчитай|рассчитай)\b", normalized)
        and re.search(r"расчет|проект|внедр|бот|агент|сделать|запуск|созвон|обсуд", normalized)
    )


def _apply_buying_milestones(
    state: dict[str, object],
    *,
    user_message: str,
    answer: str,
    roleplay_active: bool = False,
) -> None:
    if _contains_sales_pain_signal(user_message):
        state["pain_expressed"] = True
    if roleplay_active or state.get("roleplay_demo_active") or state.get(ROLEPLAY_CONTEXT_SUMMARY_KEY):
        state["demo_activated"] = True
    if _contains_price_signal(answer.casefold().replace("ё", "е")) or _contains_price_signal(user_message.casefold().replace("ё", "е")):
        state["price_exposed"] = True
    if _contains_close_consent_signal(user_message):
        state["close_consented"] = True


def _is_which_option_better_question(message: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    return bool(
        re.search(r"како[йи]|что|чего", normalized)
        and re.search(r"лучше|выгод|подойдет|подойд", normalized)
    )


def _extract_service_focus(text: str) -> str:
    normalized = text.casefold().replace("ё", "е")
    if re.search(r"авто-?корзин|checkout|оплат|корзин", normalized):
        return "cart"
    if re.search(r"агент\s+под\s+ключ|ии-?агент|ai\s+agent|crm|срм|интеграц|база\s+знаний", normalized):
        return "agent"
    if re.search(r"базов\w*\s+ассистент|ассистент|чатбот|бот", normalized):
        return "base"
    return ""


def _normalize_service_focus_value(value: object) -> str:
    text = str(value or "").strip().casefold().replace("ё", "е")
    if text in VALID_SERVICE_FOCUS:
        return text
    return _extract_service_focus(text)


def _recommended_service_from_facts(client_facts: dict[str, object]) -> str:
    goal = str(client_facts.get("automation_goal") or "").strip()
    stack = str(client_facts.get("crm_or_stack") or "").strip()
    if goal in {"smart_cart"}:
        return "cart"
    if goal in {"crm_integration", "knowledge_base", "sales_funnel"} or stack:
        return "agent"
    if client_facts.get("business_sphere") or client_facts.get("lead_channel"):
        return "base"
    return ""


def _assistant_explained_mechanism(text: str) -> bool:
    normalized = text.casefold().replace("ё", "е")
    return bool(
        re.search(r"база\s+знаний|crm|срм|интеграц|webhook|заявк|лид", normalized)
        and re.search(r"работ|переда|автоматиз|подключ", normalized)
    )


def _assistant_answered_safety(text: str) -> bool:
    normalized = text.casefold().replace("ё", "е")
    return bool(
        re.search(r"безопас|качество|надежн|доступ|данн|логир|поддерж|риск", normalized)
    )


def _should_collapse_acknowledgement_after_answer(
    *,
    message: str,
    chat_history: list[ChatHistoryMessage],
    routes: list[Route],
    sales_stage: str,
    content_followup: str,
    has_explicit_commercial_intent: bool,
) -> bool:
    if routes != [Route.general]:
        return False
    if sales_stage != "none" or content_followup != "none":
        return False
    if has_explicit_commercial_intent:
        return False
    normalized = " ".join(message.strip().split())
    if not normalized or "?" in normalized:
        return False
    if len(normalized.split()) > 4:
        return False
    previous_assistant = _last_assistant_message(chat_history)
    if not previous_assistant or "?" in previous_assistant:
        return False
    return True


def _build_acknowledgement_continuation_answer(
    *,
    client_facts: dict[str, object],
    dialog_state: dict[str, object],
) -> str:
    has_goal = bool(client_facts.get("automation_goal"))
    has_price = bool(dialog_state.get("price_base_presented") or dialog_state.get("price_cart_presented") or dialog_state.get("price_agent_presented"))

    if has_goal and not has_price:
        recommendation = _recommended_service_from_facts(client_facts)
        if recommendation == "agent":
            return "Тогда логичный следующий шаг — ИИ-агент с базой знаний и интеграцией в вашу воронку.\n\nПосчитать проект по вводным?"
        if recommendation == "cart":
            return "Тогда логичный следующий шаг — авто-корзина под ключ, чтобы клиент доходил до оплаты без ручной переписки.\n\nПосчитать проект по вводным?"
        return "Тогда начнем с базового ИИ-ассистента для приема и квалификации заявок.\n\nПосчитать проект по вводным?"

    if has_price:
        focus = str(dialog_state.get("current_product_focus") or dialog_state.get("last_offer_product") or "").strip()
        if focus in VALID_SERVICE_FOCUS:
            return f"Понял вас. Если по условиям все комфортно, можем перейти к заявке на {focus}."
        return "Понял вас. Если по условиям все комфортно, можно выбрать пакет и перейти к заявке."

    return "Понял вас."


def _remove_forbidden_traffic_question_after_milestone(
    answer: str,
    dialog_state: dict[str, object],
) -> str:
    if not (
        dialog_state.get("price_exposed")
        or dialog_state.get("demo_activated")
        or dialog_state.get("close_consented")
    ):
        return answer

    normalized_answer = (answer or "").strip()
    if not normalized_answer:
        return answer

    traffic_question_pattern = re.compile(
        r"(?:^|[\n.!?]\s*)"
        r"[^.!?\n]*(?:"
        r"откуда\s+(?:идут|приходят|пишут)?\s*(?:клиент|заявк|лид)"
        r"|где\s+(?:берете|получаете|собираете)\s*(?:клиент|заявк|лид)"
        r"|како[йе]\s+(?:у\s+вас\s+)?(?:основн\w+\s+)?(?:канал|источник)\s+(?:клиент|заявк|лид|трафик)"
        r"|(?:instagram|инстаграм|инст|whatsapp|ватсап|telegram|телеграм|сайт)[^.!?\n]*(?:клиент|заявк|лид|трафик|пишут)"
        r")[^.!?\n]*\?",
        re.IGNORECASE,
    )
    repaired = traffic_question_pattern.sub("", normalized_answer).strip()
    repaired = re.sub(r"\n{3,}", "\n\n", repaired).strip()
    if repaired == normalized_answer:
        return answer

    close_question = (
        "Давайте лучше зафиксируем спецификацию: какие 2-3 действия бот должен делать вместо менеджера?"
    )
    if close_question.casefold() in repaired.casefold():
        return repaired
    return _join_non_empty(repaired, close_question)


def _repair_forbidden_roleplay_gate_answer(answer: str, message: str) -> str:
    if _is_explicit_roleplay_command(message):
        return answer
    normalized_answer = (answer or "").casefold().replace("ё", "е")
    if not (
        "переключаюсь в режим тест-драйва" in normalized_answer
        or "жду ваш файл или текст" in normalized_answer
        or "прикрепить pdf-каталог" in normalized_answer
    ):
        return answer
    return (
        "Тест-драйв запускается только по явной команде на ролевую игру, чтобы я случайно не смешал его с обычным расчетом проекта.\n\n"
        "А по текущему вопросу можем идти дальше к спецификации: какие 2-3 действия бот должен делать вместо менеджера?"
    )


def _repair_completed_function_qualification_answer(
    *,
    answer: str,
    user_message: str,
    dialog_state: dict[str, object],
) -> str:
    if not (
        dialog_state.get("qualification_tasks_completed")
        or dialog_state.get("all_agent_functions_selected")
        or str(dialog_state.get("automation_goal") or "") in {"all_sales_agent_functions", "custom_agent_functions"}
    ):
        return answer

    normalized_answer = (answer or "").casefold().replace("ё", "е")
    repeated_question = bool(
        re.search(r"какие\s+(?:именно\s+)?(?:2-3\s+)?(?:задач|функц|действ)", normalized_answer)
        or re.search(r"что\s+из\s+этого\s+.*(?:важн|приоритет|главн)", normalized_answer)
        or re.search(r"что\s+(?:вы\s+)?хотите\s+автоматиз", normalized_answer)
        or re.search(r"(?:задач|функц|действ).{0,90}(?:наиболее|самое|приоритет)", normalized_answer)
    )
    stale_technical_question = bool(
        re.search(r"(?:какой|какая|какую|чем).{0,80}(?:crm|срм|таблиц|сайт|интеграц|канал|трафик|источник).*\?", normalized_answer)
    )

    if dialog_state.get("all_agent_functions_selected") or _is_all_functions_answer(user_message):
        intro = "Отличный подход, комплексная автоматизация дает максимальный эффект."
        captured = "В расчет включаем весь блок: база знаний, квалификация, сбор контактов и передача горячего лида менеджеру."
    else:
        goal_text = str(dialog_state.get("automation_goal_text") or user_message or "").strip()
        intro = "Да, это понятный scope для старта."
        captured = (
            f"В проект добавим: {goal_text[:180]}."
            if goal_text
            else "В проект добавим ответы клиентам, прогрев и передачу заявки менеджеру."
        )

    forced_forward = (
        f"{intro}\n\n"
        f"{captured}\n\n"
        "Базовое внедрение Plum Dev стартует от $300. Чтобы посчитать точную стоимость под ваш бюджет, давайте сделаем финальный расчет — на какой номер в WhatsApp удобнее отправить спецификацию?"
    )
    if repeated_question or (
        dialog_state.get("all_agent_functions_selected") and stale_technical_question
    ):
        return forced_forward

    has_forward_step = bool(
        re.search(r"спецификац|финальн\w*\s+расчет|расч[её]т|whatsapp|ватсап|\$300|300", normalized_answer)
    )
    if has_forward_step:
        return answer

    return _join_non_empty(answer, forced_forward)


def _sanitize_prompt_leakage_answer(answer: str) -> str:
    normalized = (answer or "").strip()
    if not normalized:
        return answer

    forbidden_line_patterns = (
        r"^\s*сбор\s+всех\s+данных\s+о\s+клиенте\s*$",
        r"^\s*квалификац(?:ия|ия\s+клиента)?\s*$",
        r"^\s*следующий\s+шаг\s*$",
        r"^\s*задача\s+ясна\.?\s*$",
        r"^\s*понял\s+задач[уы]\.?\s*$",
        r"^\s*в\s+расчет\s+бер[уе].*$",
        r"^\s*фиксируем\s+в\s+спецификац.*$",
        r"^\s*response\s+instruction\s*:?\s*$",
        r"^\s*prompt\s*:?\s*$",
        r"^\s*system\s*:?\s*$",
    )
    forbidden_inline_patterns = (
        r"что\s+обычно\s+спрашивают\s+клиенты\s+перед\s+тем,\s+как\s+замолчать\??",
        r"системн(?:ый|ого)\s+промпт",
        r"техническ(?:ие|их)\s+инструкц",
        r"переменн(?:ые|ая)\s+из\s+.*промпт",
        r"задача\s+ясна\.?",
        r"понял\s+задач[уы]\.?",
        r"в\s+расчет\s+бер[уе][^.!?\n]*[.!?]?",
        r"фиксируем\s+в\s+спецификац[^.!?\n]*[.!?]?",
    )

    kept_lines: list[str] = []
    removed = False
    for line in normalized.splitlines():
        compact = line.strip()
        lowered = compact.casefold().replace("ё", "е")
        if any(re.search(pattern, lowered) for pattern in forbidden_line_patterns):
            removed = True
            continue
        cleaned = compact
        for pattern in forbidden_inline_patterns:
            new_cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
            if new_cleaned != cleaned:
                removed = True
                cleaned = new_cleaned
        if cleaned:
            kept_lines.append(cleaned)

    repaired = "\n".join(kept_lines).strip()
    repaired = re.sub(r"\n{3,}", "\n\n", repaired).strip()
    if repaired:
        return repaired
    if removed:
        return "Продолжим без внутренней кухни.\n\nКакой вопрос сейчас важнее разобрать?"
    return answer


def _is_roleplay_output_context(
    *,
    answer: str,
    roleplay_demo_active: bool,
    dialog_state: dict[str, object],
) -> bool:
    return bool(
        roleplay_demo_active
        or dialog_state.get("roleplay_demo_active")
        or dialog_state.get(ROLEPLAY_CONTEXT_SUMMARY_KEY)
        or _looks_like_roleplay_acceptance_answer(answer)
    )


def _sanitize_roleplay_output(answer: str) -> str:
    normalized = (answer or "").strip()
    if not normalized:
        return answer

    forbidden_line_patterns = (
        r"задача\s+ясна\.?",
        r"понял\s+задач[уы]\.?",
        r"в\s+расчет\s+бер[уе][^.!?\n]*[.!?]?",
        r"фиксируем\s+в\s+спецификац[^.!?\n]*[.!?]?",
        r"закладываем\s+в\s+спецификац[^.!?\n]*[.!?]?",
        r"базовое\s+внедрение\s+plum\s+dev[^.!?\n]*[.!?]?",
        r"plum\s+dev[^.!?\n]*(?:спецификац|whatsapp|ватсап|\$300|300)[^.!?\n]*[.!?]?",
        r"[^.!?\n]*(?:на\s+какой\s+номер|whatsapp|ватсап)[^.!?\n]*(?:спецификац|расчет|расч[её]т|plum|номер)[^.!?\n]*[?!.]?",
        r"[^.!?\n]*(?:ии-?агент|ai-?агент|бот)[^.!?\n]*(?:спецификац|расчет|расч[её]т|\$300|300)[^.!?\n]*[?!.]?",
    )
    repaired = normalized
    for pattern in forbidden_line_patterns:
        repaired = re.sub(pattern, "", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"[ \t]+\n", "\n", repaired)
    repaired = re.sub(r"\n{3,}", "\n\n", repaired).strip()
    repaired = _sanitize_prompt_leakage_answer(repaired)
    if repaired:
        return _format_roleplay_b2c_answer(repaired)
    return "Продолжим в роли.\n\nКакое возражение клиента отрабатываем?"


def _format_roleplay_b2c_answer(answer: str) -> str:
    normalized = (answer or "").strip()
    if not normalized:
        return answer

    compact = " ".join(line.strip() for line in normalized.splitlines() if line.strip())
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if sentence.strip()
    ]
    if not sentences:
        return compact

    question = next((sentence for sentence in sentences if "?" in sentence), "")
    argument = next((sentence for sentence in sentences if "?" not in sentence), "")
    selected = [item for item in (argument, question) if item] or sentences[:2]

    words: list[str] = []
    for sentence in selected:
        remaining = 50 - len(words)
        if remaining <= 0:
            break
        words.extend(sentence.split()[:remaining])

    shortened = " ".join(words).strip()
    if question and "?" not in shortened:
        shortened = _join_non_empty(shortened.rstrip(".!"), question)

    lines = [
        line.strip()
        for line in re.split(r"(?<=[.!?])\s+", shortened)
        if line.strip()
    ][:4]
    return "\n\n".join(lines).strip()


def _cleanup_plum_cta_from_roleplay_answer(answer: str) -> str:
    normalized = (answer or "").strip()
    if not normalized or not _looks_like_roleplay_acceptance_answer(normalized):
        return answer

    plum_cta_pattern = re.compile(
        r"(?:^|[\n.!?]\s*)"
        r"[^.!?\n]*(?:"
        r"plum\s*dev|плам|ии-?агент|ai-?агент|спецификац|расчет|расч[её]т|\$300|300|whatsapp|ватсап"
        r")[^.!?\n]*(?:номер|спецификац|расчет|расч[её]т|стоимост|проект|бот|агент)[^.!?\n]*[?!.]?",
        re.IGNORECASE,
    )
    repaired = plum_cta_pattern.sub("", normalized).strip()
    repaired = re.sub(r"\n{3,}", "\n\n", repaired).strip()
    return repaired or normalized


def _looks_like_roleplay_acceptance_answer(answer: str) -> bool:
    normalized = (answer or "").casefold().replace("ё", "е")
    return bool(
        re.search(r"\bпринято[,! ]+\s*погнали\b", normalized)
        or re.search(r"\bпредстав(?:ьте|ь),?\s+что\s+я\b", normalized)
        or re.search(r"\b(?:включаю|запускаю|переключаюсь)\s+(?:режим\s+)?(?:продавц|менеджер|консультант|ролев|тест-драйв)", normalized)
        or re.search(r"\b(?:я\s+[-—]\s+)?(?:ваш|твой)\s+(?:продавец|менеджер|консультант)\b", normalized)
        or re.search(r"\bнапишите\s+(?:ваше\s+)?(?:сомнение|возражение|главный\s+вопрос)\b", normalized)
    )


def _ensure_sales_initiative_answer(
    *,
    answer: str,
    user_message: str,
    dialog_state: dict[str, object],
) -> str:
    normalized = (answer or "").strip()
    if not normalized:
        return answer
    if _looks_like_roleplay_acceptance_answer(normalized) or _is_explicit_roleplay_command(user_message):
        return _cleanup_plum_cta_from_roleplay_answer(normalized)
    if _phone_already_collected(user_message, dialog_state):
        return _final_contact_confirmation_answer()
    if _answer_has_live_ending(normalized):
        return answer

    if _is_all_functions_answer(user_message) or dialog_state.get("all_agent_functions_selected"):
        cta = (
            "Комплексный scope фиксируем от $300 на старте.\n\n"
            "На какой номер в WhatsApp отправить короткую спецификацию и расчет?"
        )
    elif dialog_state.get("price_exposed") or dialog_state.get("close_consented"):
        cta = "Давайте доведем это до расчета: на какой номер в WhatsApp отправить спецификацию?"
    elif _is_counter_question_to_ai_value(user_message):
        cta = "Если хотите, сразу разложу это на ваш бизнес: что сейчас сильнее всего тормозит продажи?"
    elif dialog_state.get("demo_activated"):
        cta = "Давайте посчитаем такого же ИИ-продавца под ваш продукт?"
    else:
        cta = "Давайте сделаем следующий шаг: зафиксируем, что именно должен автоматизировать бот?"

    return _join_non_empty(normalized, cta)


def _cleanup_contact_cta_after_phone_collected(
    *,
    answer: str,
    user_message: str,
    dialog_state: dict[str, object],
    client_facts: dict[str, object],
) -> str:
    if not _phone_already_collected(user_message, dialog_state, client_facts):
        return answer
    return _final_contact_confirmation_answer()


def _phone_already_collected(
    user_message: str,
    dialog_state: dict[str, object],
    client_facts: dict[str, object] | None = None,
) -> bool:
    facts = client_facts or {}
    return bool(
        _extract_phone_digits(user_message)
        or dialog_state.get("contact_phone_collected")
        or str(dialog_state.get("contact_phone") or "").strip()
        or str(facts.get("contact_phone") or "").strip()
    )


def _final_contact_confirmation_answer() -> str:
    return (
        "Отлично, номер записал!\n\n"
        "Передаю спецификацию менеджеру, он свяжется с вами в WhatsApp в течение 10 минут.\n\n"
        "На связи!"
    )


def _looks_like_final_contact_confirmation(answer: str) -> bool:
    normalized = (answer or "").casefold().replace("ё", "е")
    return bool(
        re.search(r"(номер|телефон).{0,50}(запис|зафикс|получ)", normalized)
        and re.search(r"(переда|свяж|менедж|whatsapp|ватсап)", normalized)
    )


def _answer_has_live_ending(answer: str) -> bool:
    compact = answer.strip()
    if not compact:
        return False
    last_block = compact.split("\n\n")[-1].strip().casefold().replace("ё", "е")
    if "?" in last_block:
        return True
    return bool(
        re.search(
            r"(?:/roleplay|whatsapp|ватсап|напишите|пришлите|отправьте|оставьте|скиньте|введите|давайте|зафиксируем|перейдем|рассчитаем|соберем|переходим)",
            last_block,
        )
        and not last_block.endswith(".")
    )


def _is_counter_question_to_ai_value(message: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    return bool(
        "?" in message
        and re.search(r"\b(?:зачем|почему|что|как|какую|какой)\b", normalized)
        and re.search(r"\b(?:ии|ai|бот|агент|автоматиз|нейросет|робот)\b", normalized)
    )


def _format_messenger_answer(answer: str) -> str:
    normalized = (answer or "").strip()
    if not normalized:
        return answer

    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    raw_paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n+", normalized)
        if paragraph.strip()
    ]
    formatted: list[str] = []
    for paragraph in raw_paragraphs:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if _looks_like_list_block(lines):
            formatted.append("\n".join(lines))
            continue

        compact = " ".join(lines)
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", compact)
            if sentence.strip()
        ]
        if len(sentences) <= 2:
            formatted.append(compact)
            continue

        for index in range(0, len(sentences), 2):
            formatted.append(" ".join(sentences[index : index + 2]).strip())

    return "\n\n".join(part for part in formatted if part).strip()


def _looks_like_list_block(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    list_marker = re.compile(r"^\s*(?:[•*\-]|\d+[.)]|[^\w\s])")
    return any(list_marker.search(line) for line in lines)


def _repair_stage_3_price_answer(answer: str, dialog_state: dict[str, object]) -> str:
    normalized = answer.strip()
    if not normalized:
        return answer

    lines = [line.rstrip() for line in normalized.splitlines()]
    kept: list[str] = []
    removed_qualification_question = False
    qualification_question = re.compile(
        r"(какая|какой|сколько|укажите|подскажите).{0,70}(ниша|сфера|канал|crm|срм|сайт|заявк)",
        re.IGNORECASE,
    )
    for line in lines:
        compact = line.strip()
        if "?" in compact and qualification_question.search(compact.casefold().replace("ё", "е")):
            removed_qualification_question = True
            continue
        kept.append(line)

    repaired = "\n".join(kept).strip()
    repaired = _ensure_expected_stage_3_prices(repaired, dialog_state)
    focus = str(dialog_state.get("last_offer_product") or dialog_state.get("current_product_focus") or "").strip()
    if focus in VALID_SERVICE_FOCUS:
        next_question = f"Начнем с пакета {focus}?"
    else:
        next_question = "Какой вариант кажется комфортнее для старта?"
    if not removed_qualification_question and "?" in repaired[-120:]:
        return answer
    if repaired and "?" not in repaired[-120:]:
        repaired = f"{repaired}\n\n{next_question}"
    return repaired or next_question


def _repair_which_option_better_answer(answer: str, client_facts: dict[str, object]) -> str:
    recommendation = _recommended_service_from_facts(client_facts)
    if recommendation == "agent":
        return "Я бы выбрал ИИ-агента под ключ: он закрывает не только ответы, но и базу знаний, квалификацию и передачу заявок.\n\nСобрать расчет по этому варианту?"
    if recommendation == "cart":
        return "Я бы начал с авто-корзины: она быстрее всего убирает ручной этап между интересом клиента и оплатой.\n\nСобрать расчет по этому варианту?"
    return "Я бы начал с базового ИИ-ассистента: это быстрый способ проверить эффект без тяжелого внедрения.\n\nСобрать расчет по этому варианту?"


def _ensure_expected_stage_3_prices(answer: str, dialog_state: dict[str, object]) -> str:
    normalized = answer.casefold().replace("ё", "е")
    basis = str(dialog_state.get("last_offer_basis") or "")
    focus = str(dialog_state.get("last_offer_product") or dialog_state.get("current_product_focus") or "").strip()
    wants_both = basis in {"both_options", "service_options"} or (not focus and "вариант" in " ".join(str(item) for item in dialog_state.get("asked_offers", [])))
    if not wants_both:
        return answer
    has_service_price = bool(re.search(r"\d[\d\s]{2,}", normalized))
    if has_service_price:
        return answer

    price_line = "Нужно быстро уточнить вводные, чтобы посчитать проект без выдуманных цифр."
    if not answer.strip():
        return price_line
    return f"{answer.strip()}\n\n{price_line}"


def _select_checkout_product(
    *,
    products: list[ProductCard],
    message: str,
    chat_history: list[ChatHistoryMessage],
    client_facts: dict[str, object],
    dialog_state: dict[str, object] | None = None,
) -> ProductCard | None:
    if not products:
        return None

    state = dialog_state or {}
    state_focus = str(
        state.get("last_offer_product") or state.get("current_product_focus") or ""
    ).strip()
    if state_focus in VALID_SERVICE_FOCUS:
        product = _find_product_by_service_focus(products, state_focus)
        if product:
            return product

    current_text = message.casefold().replace("ё", "е")
    current_focus = _extract_service_focus(current_text)
    if current_focus:
        product = _find_product_by_service_focus(products, current_focus)
        if product:
            return product

    searchable_text = " ".join(
        [
            message,
            *[item.content for item in chat_history[-6:]],
            str(client_facts.get("offer") or ""),
            str(client_facts.get("automation_goal") or ""),
        ]
    ).casefold().replace("ё", "е")

    searchable_focus = _extract_service_focus(searchable_text)
    if searchable_focus:
        product = _find_product_by_service_focus(products, searchable_focus)
        if product:
            return product

    recommended = _recommended_service_from_facts(client_facts)
    preferred = _find_product_by_service_focus(products, recommended) if recommended else None
    return preferred or products[0]


def _find_product_by_service_focus(
    products: list[ProductCard],
    service_focus: str,
) -> ProductCard | None:
    for product in products:
        haystack = f"{product.product_id} {product.dosage or ''} {product.title}".casefold()
        if service_focus == "cart" and re.search(r"cart|checkout|корзин|оплат", haystack):
            return product
        if service_focus == "agent" and re.search(r"agent|агент|crm|срм|интеграц|knowledge|база", haystack):
            return product
        if service_focus == "base" and re.search(r"base|basic|баз|ассистент|бот|chatbot", haystack):
            return product
    return None


def _checkout_product_service_focus(product: ProductCard) -> str:
    haystack = f"{product.product_id} {product.dosage or ''} {product.title}".casefold().replace("ё", "е")
    if re.search(r"cart|checkout|корзин|оплат", haystack):
        return "cart"
    if re.search(r"agent|агент|crm|срм|интеграц|knowledge|база", haystack):
        return "agent"
    if re.search(r"base|basic|баз|ассистент|бот|chatbot", haystack):
        return "base"
    return ""


def _with_checkout_product_image(product: ProductCard | None) -> ProductCard | None:
    if product is None:
        return None

    service_focus = _checkout_product_service_focus(product)
    image_url = AI_SERVICE_IMAGE_URLS.get(service_focus)
    if not image_url:
        return product

    return product.model_copy(update={"image_url": image_url})


def _base_ai_assistant_checkout_product(products: list[ProductCard]) -> ProductCard:
    product = _find_product_by_service_focus(products, "base")
    if product is None:
        product = ProductCard(
            product_id="ai-assistant-basic",
            title="Базовый ИИ-ассистент",
            dosage=None,
            price_tenge=None,
        )

    return product.model_copy(
        update={
            "title": product.title or "Базовый ИИ-ассистент",
            "dosage": product.dosage,
            "price_tenge": product.price_tenge,
        }
    )


def _build_forced_base_assistant_cart_answer() -> str:
    return (
        "Отлично. Для быстрого старта подойдет базовый ИИ-ассистент: он примет заявки, "
        "ответит на частые вопросы и передаст горячих клиентов дальше. Карточку для перехода прикрепил(а) ниже."
    )


def _build_create_cart_answer(product: ProductCard) -> str:
    return (
        f"Отлично, сформировал для вас заявку на {product.title}. "
        "Переходите по кнопке ниже, чтобы продолжить оформление."
    )


def _build_log_metadata(response: ChatResponse) -> dict[str, Any]:
    metadata = dict(response.metadata)
    if response.checkout:
        metadata["checkout"] = True
    if response.product_id:
        metadata["product_id"] = response.product_id
    if response.product:
        metadata["product"] = response.product.model_dump(exclude_none=True)
    return metadata


def _checkout_contact_guard_answer(
    *,
    message: str,
    chat_history: list[ChatHistoryMessage],
    answer: str,
    client_facts: dict[str, object],
) -> str | None:
    if _message_has_phone_and_project_detail(message):
        return None

    context_collects_contacts = _has_contact_collection_context(chat_history)
    placeholder_reply = _is_contact_placeholder_reply(message)
    false_completion = _claims_checkout_completed(answer)

    if not false_completion and not (context_collects_contacts and placeholder_reply):
        return None

    name = _extract_client_name(message, chat_history, client_facts)
    prefix = f"{name}, я с радостью оформлю заявку" if name else "Я с радостью оформлю заявку"
    return (
        f"{prefix}, но вы, кажется, забыли написать сами контакты) Пожалуйста, укажите "
        "телефон для связи и пару слов о бизнесе или ссылку на сайт/Instagram."
    )


def _has_contact_collection_context(chat_history: list[ChatHistoryMessage]) -> bool:
    recent_assistant = "\n".join(
        item.content for item in chat_history[-6:] if item.role == "assistant"
    ).casefold()
    if not recent_assistant:
        return False

    return any(
        re.search(pattern, recent_assistant, re.IGNORECASE)
        for pattern in CONTACT_COLLECTION_PATTERNS
    )


def _claims_checkout_completed(answer: str) -> bool:
    normalized = (answer or "").casefold()
    return any(
        re.search(pattern, normalized, re.IGNORECASE)
        for pattern in CHECKOUT_COMPLETED_PATTERNS
    )


def _is_contact_placeholder_reply(message: str) -> bool:
    normalized = (message or "").strip().casefold()
    if not normalized:
        return True
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in CONTACT_PLACEHOLDER_PATTERNS):
        return True
    if not re.search(r"\d", normalized) and len(normalized.split()) <= 3:
        return any(
            marker in normalized
            for marker in ("напис", "отправ", "лови", "да", "ок", "готов")
        )
    return False


def _message_has_phone_and_project_detail(message: str) -> bool:
    normalized = (message or "").strip()
    if not normalized:
        return False

    digits = _extract_phone_digits(normalized)
    if not digits:
        return False

    return bool(PROJECT_DETAIL_PATTERN.search(normalized))


def _ru_words_to_int(word_tokens: list[str]) -> int | None:
    """Parse a short list of Russian number words (up to 3 tokens) into an integer.

    Handles patterns like ["девятьсот", "девяносто", "девять"] → 999.
    Returns None if any token is unrecognised.
    """
    total = 0
    for w in word_tokens:
        if w in _RU_HUNDREDS:
            total += _RU_HUNDREDS[w]
        elif w in _RU_TENS:
            total += _RU_TENS[w]
        elif w in _RU_ONES_MAP:
            total += _RU_ONES_MAP[w]
        else:
            return None
    return total


def _extract_phone_from_words(text: str) -> str:
    """Extract a phone number written as Russian words.

    Handles patterns like "плюс семь девятьсот девяносто девять сто двадцать три..."
    Returns a raw digit string (no spaces/dashes) or "" if nothing phone-like found.
    """
    normalized = text.lower()
    # Tokenise: keep Cyrillic words and literal '+'
    tokens = re.findall(r"[а-яё]+|[+]", normalized)

    # Replace 'плюс' with a sentinel so we can detect it without special-casing later
    tokens = ["+" if t == "плюс" else t for t in tokens]

    has_plus = False
    number_groups: list[int] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "+":
            has_plus = True
            i += 1
            continue
        if tok in _RU_HUNDREDS:
            val = _RU_HUNDREDS[tok]
            i += 1
            if i < len(tokens) and tokens[i] in _RU_TENS:
                val += _RU_TENS[tokens[i]]
                i += 1
            if i < len(tokens) and tokens[i] in _RU_ONES_MAP:
                ones_val = _RU_ONES_MAP[tokens[i]]
                if ones_val < 20:  # guard: not a second hundred-block sneaking in
                    val += ones_val
                    i += 1
            number_groups.append(val)
        elif tok in _RU_TENS:
            val = _RU_TENS[tok]
            i += 1
            if i < len(tokens) and tokens[i] in _RU_ONES_MAP:
                ones_val = _RU_ONES_MAP[tokens[i]]
                if ones_val < 20:
                    val += ones_val
                    i += 1
            number_groups.append(val)
        elif tok in _RU_ONES_MAP:
            number_groups.append(_RU_ONES_MAP[tok])
            i += 1
        else:
            # Non-number word: break if we already have enough digits, otherwise reset
            digit_so_far = "".join(str(g) for g in number_groups)
            if len(digit_so_far) >= 7:
                break
            number_groups = []
            has_plus = False
            i += 1

    digit_str = "".join(str(g) for g in number_groups)
    if len(digit_str) < 7:
        return ""
    if has_plus and not digit_str.startswith("7"):
        digit_str = "7" + digit_str
    return digit_str


def _extract_phone_digits(text: str) -> str:
    match = PHONE_PATTERN.search(text or "")
    if match:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 7:
            return digits
    # Fallback: phone written as Russian words
    return _extract_phone_from_words(text or "")


def _extract_client_name(
    message: str,
    chat_history: list[ChatHistoryMessage],
    client_facts: dict[str, object],
) -> str:
    for key in ("name", "first_name", "client_name"):
        value = str(client_facts.get(key) or "").strip()
        if _looks_like_name(value):
            return value.split()[0]

    search_text = "\n".join(
        [*(item.content for item in chat_history[-10:]), message]
    )
    patterns = (
        r"(?:меня\s+зовут|я\s+)\s+([А-ЯЁ][а-яё]{2,20})\b",
        r"\b([А-ЯЁ][а-яё]{2,20}),\s+я\s+вижу",
    )
    for pattern in patterns:
        match = re.search(pattern, search_text)
        if match and _looks_like_name(match.group(1)):
            return match.group(1)

    return ""


def _looks_like_name(value: str) -> bool:
    if not value:
        return False
    first = value.strip().split()[0]
    return bool(re.fullmatch(r"[А-ЯЁA-Z][а-яёa-z]{2,20}", first))


def _merge_client_facts_for_request(
    *,
    gemini: GeminiService,
    session_metadata: dict[str, Any],
    fact_scan_history: list[ChatHistoryMessage],
    message: str,
) -> dict[str, object]:
    stored_facts = session_metadata.get("client_facts") or {}
    if not isinstance(stored_facts, dict):
        stored_facts = {}

    facts = gemini.extract_client_facts(
        fact_scan_history,
        current_message=message,
        existing_facts=stored_facts,
    )
    phone = _extract_phone_digits(message)
    if phone:
        facts["contact_phone"] = phone
    return _normalize_client_facts(facts)


def _normalize_client_facts(facts: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    text_fields = {
        "business_sphere",
        "lead_channel",
        "crm_or_stack",
        "website_or_social",
        "automation_goal",
        "offer",
        "name",
        "first_name",
        "client_name",
        "contact_phone",
    }

    for key in text_fields:
        value = str(facts.get(key) or "").strip()
        if value:
            normalized[key] = value[:160]

    return normalized


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    match = re.search(r"\d{1,3}", str(value))
    if not match:
        return None
    return int(match.group(0))


def _select_primary_route(routes: list[Route]) -> Route:
    if Route.rag_required in routes:
        return Route.rag_required
    if Route.checkout in routes:
        return Route.checkout
    return routes[0] if routes else Route.rag_required


def _trim_chat_history(
    chat_history: list[ChatHistoryMessage],
    max_messages: int,
) -> list[ChatHistoryMessage]:
    if max_messages <= 0:
        return []

    return chat_history[-max_messages:]


def _build_effective_history(
    *,
    logged_history: list[ChatHistoryMessage],
    payload_history: list[ChatHistoryMessage],
    max_messages: int,
    reset_context: bool,
) -> list[ChatHistoryMessage]:
    if reset_context:
        return []

    return _merge_chat_history(
        logged_history,
        payload_history,
        max_messages,
    )


def _merge_chat_history(
    server_history: list[ChatHistoryMessage],
    payload_history: list[ChatHistoryMessage],
    max_messages: int,
) -> list[ChatHistoryMessage]:
    merged: list[ChatHistoryMessage] = []
    seen: set[tuple[str, str]] = set()
    for item in [*server_history, *payload_history]:
        content = item.content.strip()
        if not content:
            continue
        key = (item.role, content)
        if key in seen:
            continue
        seen.add(key)
        merged.append(ChatHistoryMessage(role=item.role, content=content))

    return _trim_chat_history(merged, max_messages)


def _should_use_memory_context(payload: ChatRequest, gemini: GeminiService) -> bool:
    return (
        gemini.settings.enable_b2b_memory_summary
        and len(payload.chat_history) >= gemini.settings.max_history_messages
    )


def _should_refresh_memory(
    payload: ChatRequest,
    gemini: GeminiService,
    is_new_session: bool,
) -> bool:
    return (
        not is_new_session
        and gemini.settings.enable_b2b_memory_summary
        and len(payload.chat_history) >= gemini.settings.max_history_messages
    )


def _is_new_session(last_message_at: datetime | None) -> bool:
    if last_message_at is None:
        return True

    return datetime.now(timezone.utc) - last_message_at > SESSION_TIMEOUT


def _check_rate_limit(channel: str, chat_id: str) -> None:
    now = time.time()
    key = f"{channel}:{chat_id}"
    recent_requests = [
        timestamp
        for timestamp in RATE_LIMIT_BUCKETS.get(key, [])
        if now - timestamp < RATE_LIMIT_WINDOW_SECONDS
    ]

    if len(recent_requests) >= RATE_LIMIT_MAX_REQUESTS:
        RATE_LIMIT_BUCKETS[key] = recent_requests
        logger.warning(
            "Rate limit exceeded for key=%s count=%s window_seconds=%s",
            key,
            len(recent_requests),
            RATE_LIMIT_WINDOW_SECONDS,
        )
        raise HTTPException(
            status_code=429,
            detail=RATE_LIMIT_DETAIL,
        )

    recent_requests.append(now)
    RATE_LIMIT_BUCKETS[key] = recent_requests


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
    if isinstance(exc, GeminiQuotaExhausted):
        return True

    error_text = str(exc)
    return (
        "RESOURCE_EXHAUSTED" in error_text
        or "429" in error_text
        or "local RPM/TPM/RPD limits" in error_text
    )
