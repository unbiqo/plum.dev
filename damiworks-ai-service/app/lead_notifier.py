"""Owner lead notifications for the DamiWorks website consultant.

Sends Telegram messages to the owner (via the repurposed damiworks_tg_bot token)
when a lead is created (intake completed) and when contact is collected. Two
distinct messages — a "Новый лид" is never sent twice; the contact event is a
"Лид обновлён".

All sending is best-effort: failures are logged and swallowed so the user chat
is never affected.
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.request as urllib_request

logger = logging.getLogger("damiworks.lead_notifier")


def _fmt_list(value: object) -> str:
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(items) if items else "—"
    text = str(value).strip() if value is not None else ""
    return text or "—"


def _fmt(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "—"


def _interest_emoji(interest_level: object) -> str:
    level = str(interest_level or "").strip().lower()
    if level == "hot":
        return "🔥"
    if level == "warm":
        return "✅"
    return "🔵"


def format_lead_created(lead: dict) -> str:
    """First notification — intake completed, waiting for contact."""
    emoji = _interest_emoji(lead.get("interest_level"))
    return "\n".join(
        [
            f"{emoji} Новый лид DamiWorks",
            "",
            f"Пакет: {_fmt(lead.get('package_recommended'))}",
            f"Бизнес: {_fmt(lead.get('business_type'))}",
            f"Каналы: {_fmt_list(lead.get('channels'))}",
            f"Задачи: {_fmt_list(lead.get('tasks'))}",
            f"Объём: {_fmt(lead.get('volume'))}/день",
            f"Запуск: {_fmt(lead.get('timeline'))}",
            "",
            "Контакт: пока нет",
            "Статус: ждём контакт",
        ]
    )


def format_lead_updated(lead: dict) -> str:
    """Second notification — contact received. Clearly an update, not a new lead."""
    package = lead.get("package_selected") or lead.get("package_recommended")
    return "\n".join(
        [
            "📝 Лид обновлён — контакт получен",
            "",
            f"Пакет: {_fmt(package)}",
            f"Бизнес: {_fmt(lead.get('business_type'))}",
            f"Каналы: {_fmt_list(lead.get('channels'))}",
            f"Задачи: {_fmt_list(lead.get('tasks'))}",
            f"Объём: {_fmt(lead.get('volume'))}/день",
            f"Запуск: {_fmt(lead.get('timeline'))}",
            "",
            f"Контакт: {_fmt(lead.get('user_contact_name') or lead.get('contact_raw'))}",
            f"Телефон: {_fmt(lead.get('user_contact_phone'))}",
            f"Telegram: {_fmt(lead.get('user_contact_telegram'))}",
            "",
            "Статус: готов к связи",
        ]
    )


def format_english_school_lead(lead: dict) -> str:
    """Contact collected from the English School demo chat."""
    state = lead.get("_school_state") or {}
    return "\n".join(
        [
            "🏫 Demo лид — English School",
            "",
            f"Контакт: {_fmt(lead.get('contact_raw'))}",
            f"Программа: {_fmt(state.get('program'))}",
            f"Формат: {_fmt(state.get('format_preference'))}",
            f"Возраст: {_fmt(state.get('student_age'))}",
            f"Город: {_fmt(state.get('city'))}",
            f"Расписание: {_fmt(state.get('preferred_schedule'))}",
            "",
            "Статус: контакт получен в демо",
        ]
    )


def format_medical_center_lead(lead: dict) -> str:
    """Contact collected from the Medical Center demo chat (MedNova Clinic)."""
    state = lead.get("_clinic_state") or {}
    urgency = str(state.get("urgency_flag") or "normal")
    header = "🏥 Demo лид — MedNova Clinic"
    if urgency != "normal":
        header = f"⚠️ {header}"
    return "\n".join(
        [
            header,
            "",
            f"Контакт: {_fmt(lead.get('contact_raw'))}",
            f"Пациент: {_fmt(state.get('patient_name'))}",
            f"Имя контакта: {_fmt(state.get('contact_name'))}",
            f"Возраст: {_fmt(state.get('age'))}",
            f"Направление: {_fmt(state.get('specialty'))}",
            f"Жалоба/цель: {_fmt(state.get('symptoms_or_goal'))}",
            f"Удобное время: {_fmt(state.get('preferred_time'))}",
            f"Срочность: {_fmt(urgency)}",
            "",
            f"Статус: {_fmt(lead.get('status'))}",
        ]
    )


def format_contact_form_lead(lead: dict) -> str:
    """Contact-section footer form submission."""
    return "\n".join(
        [
            "📬 Заявка с сайта",
            "",
            f"Имя: {_fmt(lead.get('user_contact_name'))}",
            f"Контакт: {_fmt(lead.get('contact_raw'))}",
            f"Бизнес: {_fmt(lead.get('business_type'))}",
            f"Сообщение: {_fmt(lead.get('summary'))}",
            "",
            "Статус: новая заявка",
        ]
    )


def _send_sync(bot_token: str, chat_id: str, text: str) -> None:
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib_request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=5):
        return


async def send_owner_notification(bot_token: str, chat_id: str, text: str) -> bool:
    """Best-effort owner notification. Returns True if the message was sent.

    No-ops (returns False) when the bot is not configured. Never raises.
    """
    if not bot_token or not chat_id:
        logger.info("Lead notification skipped (Telegram not configured):\n%s", text)
        return False
    try:
        await asyncio.to_thread(_send_sync, bot_token, chat_id, text)
        return True
    except Exception:
        logger.exception("Failed to send owner lead notification")
        return False
