from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from config import config


logger = logging.getLogger(__name__)

SERVICE_UNAVAILABLE_TEXT = (
    "Сервис настраивается или просыпается. "
    "Пожалуйста, подождите минуту и повторите сообщение."
)
MAX_ATTACHMENT_BYTES = 6 * 1024 * 1024
MAX_ATTACHMENT_MB = MAX_ATTACHMENT_BYTES // (1024 * 1024)


bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


def _build_payload(
    *,
    chat_id: int,
    text: str,
    reset_context: bool,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "channel": "telegram",
        "chat_id": str(chat_id),
        "instance_id": config.INSTANCE_ID,
        "message": text,
        "chat_history": [],
        "reset_context": reset_context,
        "attachments": attachments or [],
    }


async def _request_ai_service(payload: dict[str, Any]) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(config.AI_SERVICE_URL, json=payload)
        response.raise_for_status()
        data = response.json()

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        logger.warning("AI service returned response without answer: %r", data)
        return SERVICE_UNAVAILABLE_TEXT

    return answer


async def _send_ai_answer(
    message: Message,
    *,
    text: str,
    reset_context: bool,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    payload = _build_payload(
        chat_id=message.chat.id,
        text=text,
        reset_context=reset_context,
        attachments=attachments,
    )

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except Exception:
        logger.debug("Failed to send Telegram typing action", exc_info=True)

    try:
        answer = await _request_ai_service(payload)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
        logger.warning("AI service request failed: %s", exc)
        answer = SERVICE_UNAVAILABLE_TEXT
    except Exception:
        logger.exception("Unexpected AI service error")
        answer = SERVICE_UNAVAILABLE_TEXT

    await message.answer(answer, parse_mode=ParseMode.HTML)


@dp.message(Command("start", "reset"))
async def handle_start_or_reset(message: Message) -> None:
    await _send_ai_answer(
        message,
        text="Привет!",
        reset_context=True,
    )


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    await _send_ai_answer(
        message,
        text=message.text or "",
        reset_context=False,
    )


async def _download_telegram_file_base64(file_id: str) -> str:
    file = await bot.get_file(file_id)
    if not file.file_path:
        raise RuntimeError("Telegram returned file without file_path")

    url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    if len(response.content) > MAX_ATTACHMENT_BYTES:
        raise RuntimeError(f"Downloaded Telegram file exceeds {MAX_ATTACHMENT_MB} MB")

    return base64.b64encode(response.content).decode("ascii")


@dp.message(F.document | F.photo)
async def handle_attachment(message: Message) -> None:
    attachments: list[dict[str, Any]] = []
    text = message.caption or ""

    try:
        if message.document:
            if message.document.file_size and message.document.file_size > MAX_ATTACHMENT_BYTES:
                await message.answer(f"Файл слишком большой. Пришлите PDF/скрин до {MAX_ATTACHMENT_MB} МБ.")
                return
            attachments.append(
                {
                    "filename": message.document.file_name,
                    "mime_type": message.document.mime_type or "application/octet-stream",
                    "base64_data": await _download_telegram_file_base64(message.document.file_id),
                }
            )
        elif message.photo:
            photo = message.photo[-1]
            if photo.file_size and photo.file_size > MAX_ATTACHMENT_BYTES:
                await message.answer(f"Фото слишком большое. Пришлите скрин до {MAX_ATTACHMENT_MB} МБ.")
                return
            attachments.append(
                {
                    "filename": "telegram-photo.jpg",
                    "mime_type": "image/jpeg",
                    "base64_data": await _download_telegram_file_base64(photo.file_id),
                }
            )
    except Exception:
        logger.exception("Failed to download Telegram attachment")
        await message.answer("Не смог скачать файл из Telegram. Попробуйте отправить его еще раз.")
        return

    await _send_ai_answer(
        message,
        text=text,
        reset_context=False,
        attachments=attachments,
    )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
