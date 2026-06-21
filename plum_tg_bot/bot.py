from __future__ import annotations

import asyncio
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
) -> dict[str, Any]:
    return {
        "channel": "telegram",
        "chat_id": str(chat_id),
        "instance_id": config.INSTANCE_ID,
        "message": text,
        "chat_history": [],
        "reset_context": reset_context,
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
) -> None:
    payload = _build_payload(
        chat_id=message.chat.id,
        text=text,
        reset_context=reset_context,
    )

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


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
