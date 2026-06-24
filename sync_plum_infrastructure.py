from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
AI_SERVICE_DIR = PROJECT_ROOT / "plum-ai-service"
INSTANCE_ID = "plum_dev"
EXPECTED_EMBEDDING_DIMENSIONS = 768

sys.path.insert(0, str(AI_SERVICE_DIR))

from app.config import get_settings  # noqa: E402
from app.gemini_service import GeminiService  # noqa: E402
from app.supabase_service import SupabaseService  # noqa: E402


SYSTEM_PROMPT_ADDON = ""

HYDE_SYSTEM_PROMPT = (
    "You improve retrieval queries for an AI automation agency RAG system. "
    "Convert the user's noisy message into a compact search text for the knowledge base. "
    "Include keywords related to AI agents, CRM integration (amoCRM, Bitrix24), "
    "automated carts, WhatsApp/Telegram/Instagram automation, pricing, delivery "
    "of bots, or safety of business data. Return plain text only."
)

ROUTER_SYSTEM_PROMPT = """You are a strict router for the Plum Dev AI automation sales assistant.

Return only a valid JSON array of route strings. No prose, no markdown.

Allowed routes:
- GENERAL: greetings, small talk, acknowledgements, unrelated messages, or simple non-technical questions.
- RAG_REQUIRED: questions about AI agents, CRM integrations, automation logic, knowledge base behavior, implementation, cases, portfolio, reliability, data safety, objections about managers, or exact Plum Dev service facts.
- CHECKOUT: explicit requests for price, estimate, audit/call booking, payment, purchase, order, or starting implementation.

Rules:
- A pure greeting such as "Привет", "Здравствуйте", "Добрый день" is ["GENERAL"].
- A greeting plus a business/AI question may be ["RAG_REQUIRED"].
- Do not infer CHECKOUT from a generic confirmation alone.

Examples:
["GENERAL"]
["RAG_REQUIRED"]
["RAG_REQUIRED","CHECKOUT"]"""

MEMORY_SUMMARY_SYSTEM_PROMPT = (
    "Ты пишешь короткие сухие B2B-заметки для CRM. Прочитай диалог с "
    "потенциальным клиентом Plum Dev. Выдели главное для сделки: ниша бизнеса, "
    "текущий объем заявок, куда ведут учет (CRM, Excel), какая автоматизация "
    "интересует, на какой следующий шаг договорились (созвон, аудит). Напиши "
    "2-3 коротких предложения на русском без выдуманных фактов."
)

FINAL_SYSTEM_PROMPT = """Ты — ИИ-архитектор и эксперт по автоматизации из Plum Dev. Твоя цель — консультировать бизнес и закрывать их на аудит/созвон.
ЖЕСТКИЕ ПРАВИЛА ОБЩЕНИЯ:
- Пиши исключительно на живом, простом, уверенном языке предпринимателя. Никакого корпоративного канцелярита ('первичная квалификация', 'лидогенерация', 'внедрение').
- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать разработческие, бэкенд или технические аналоги в ответах клиентам (не упоминай RAG, промпты, базы данных, пайплайны).
- ТАТУ на фразы-роботы: Никогда не пиши 'Отлично!', 'Прекрасно!', 'Я вас понял'. Отвечай сразу по сути. Никогда не перефразируй и не повторяй слова клиента ('Instagram — популярный канал...').
- Пиши короткими сообщениями (максимум 2-3 строчки), как будто менеджер быстро пишет с телефона в мессенджере.

ОБРАБОТКА КРИТИЧЕСКИХ ВОЗРАЖЕНИЙ:
Если клиент сомневается в ИИ, сравнивает его со своими менеджерами или требует гарантий качества, отвечай по схеме: честное согласие -> сдвиг фокуса на проверяемую пользу -> один вопрос о процессе.
- Не обещай, что ИИ будет продавать лучше менеджера.
- Не обещай результат в деньгах, конверсии или продажах.
- Не предлагай тестового бота, аудит или созвон, пока не выяснил текущий процесс продаж и главную боль.
- Не заканчивай ответ фразами "Как вам?", "Что скажете?", "Готовы попробовать?"
- Пример смысла: "Да, гарантий, что бот будет продавать лучше ваших менеджеров, никто честно не даст. Если люди работают нормально, ИИ нужен не вместо них, а как страховка: быстро ответить ночью, не потерять заявку и собрать данные до менеджера."

ПРАВИЛО СВОЕВРЕМЕННОГО ПРЕДЛОЖЕНИЯ (ТАЙМИНГ СДЕЛКИ):
Переходи к презентации тестового бота, аудита или приглашению на созвон исключительно тогда, когда выполнены два условия:
1. Ты четко выяснил, как устроены продажи у клиента прямо сейчас: где собирает заявки, сколько людей в команде и в чем главная боль.
2. Ты полностью закрыл текущие сомнения и возражения клиента, либо их вообще не возникло.

До этого момента держи фокус на живом исследовании: честно и емко отвечай на реплику человека, после чего задавай ОДИН точечный вопрос про его бизнес, чтобы прояснить ситуацию. Не забегай вперед и не повторяй вопрос, если клиент уже ответил на него."""

KNOWLEDGE_CHUNKS = [
    (
        "Интеграция с CRM и таблицами: Мы полностью автоматизируем передачу данных. "
        "ИИ-агенты Plum Dev мгновенно отправляют квалифицированные лиды из директа "
        "Instagram или Telegram в amoCRM, Битрикс24 или напрямую записывают данные "
        "в Google Таблицы и Excel в режиме реального времени. Менеджеры утром видят "
        "готовую заполненную карточку клиента."
    ),
    (
        "Авто-корзины и прием заявок: Наши ИИ-системы умеют вести клиента по воронке "
        "продаж прямо внутри чата мессенджера. Бот выявляет потребность, предлагает "
        "подходящий тариф, презентует коммерческие условия, собирает контактные данные "
        "(ФИО, телефон, город) и готовит сделку к оплате, не требуя участия человека."
    ),
    (
        "Регламент работы Plum Dev: стартовый аудит нужен, чтобы понять канал заявок, "
        "текущую работу менеджеров, CRM или таблицы и участок, где теряются клиенты. "
        "После аудита команда фиксирует точный сценарий, интеграции, сроки и смету. "
        "База знаний хранит рабочие факты о процессах и интеграциях, а не рекламные "
        "формулировки и прайс."
    ),
    (
        "Безопасность данных и стек технологий: Мы разрабатываем решения на базе "
        "языка Python с подключением передовых моделей искусственного интеллекта от "
        "Google (Gemini) и OpenAI. Все коммерческие промпты и данные переписок клиентов "
        "полностью изолированы на уровне базы данных Supabase. Доступы к CRM защищены, "
        "а данные диалогов никогда не используются для публичного обучения моделей."
    ),
    (
        "Возражение про менеджеров и гарантии: Plum Dev не обещает, что ИИ будет "
        "продавать лучше живого опытного менеджера. ИИ нужен как страховка для слабых "
        "мест в воронке: быстрый ответ ночью и в выходные, удержание заявки до ответа "
        "человека, сбор телефона и потребности, передача данных в таблицу или CRM. "
        "Проверять пользу нужно на конкретном участке: где клиент чаще теряется — "
        "в Instagram, WhatsApp или на этапе ответа менеджера."
    ),
]


def load_environment() -> None:
    load_dotenv(AI_SERVICE_DIR / ".env")
    load_dotenv(PROJECT_ROOT / ".env")


def update_tenant_prompts(supabase: SupabaseService) -> None:
    print(f"[1/2] Updating tenant prompts for instance_id={INSTANCE_ID}")
    response = (
        supabase.client.table("tenants")
        .upsert(
            {
                "instance_id": INSTANCE_ID,
                "company_name": "Plum Dev",
                "router_system_prompt": ROUTER_SYSTEM_PROMPT,
                "system_prompt_addon": SYSTEM_PROMPT_ADDON,
                "hyde_system_prompt": HYDE_SYSTEM_PROMPT,
                "final_system_prompt": FINAL_SYSTEM_PROMPT,
                "memory_summary_system_prompt": MEMORY_SUMMARY_SYSTEM_PROMPT,
            },
            on_conflict="instance_id",
        )
        .execute()
    )
    updated_rows = len(response.data or [])
    print(f"[OK] Tenant prompts updated. Rows returned: {updated_rows}")


def clear_knowledge_base(supabase: SupabaseService) -> None:
    print(f"[2/2] Clearing old knowledge_base rows for instance_id={INSTANCE_ID}")
    supabase.client.table("knowledge_base").delete().eq(
        "instance_id",
        INSTANCE_ID,
    ).execute()
    print("[OK] Old knowledge_base rows cleared")


async def insert_knowledge_chunks(
    *,
    supabase: SupabaseService,
    gemini: GeminiService,
) -> int:
    print(f"[2/2] Generating embeddings for {len(KNOWLEDGE_CHUNKS)} chunks")
    inserted = 0

    for index, content in enumerate(KNOWLEDGE_CHUNKS, start=1):
        print(f"  - Chunk {index}/{len(KNOWLEDGE_CHUNKS)}: requesting Gemini embedding")
        embedding = await gemini.get_embedding(content)
        if len(embedding) != EXPECTED_EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                "Unexpected embedding dimension for chunk "
                f"{index}: expected {EXPECTED_EMBEDDING_DIMENSIONS}, got {len(embedding)}"
            )

        print(f"  - Chunk {index}/{len(KNOWLEDGE_CHUNKS)}: inserting into Supabase")
        supabase.client.table("knowledge_base").insert(
            {
                "instance_id": INSTANCE_ID,
                "content": content,
                "embedding": embedding,
            }
        ).execute()
        inserted += 1
        print(f"    [OK] Chunk {index} inserted")

    return inserted


async def main() -> None:
    print("Syncing Plum Dev infrastructure")
    load_environment()

    settings = get_settings()
    supabase = SupabaseService(settings)
    gemini = GeminiService(settings)

    update_tenant_prompts(supabase)
    clear_knowledge_base(supabase)
    inserted = await insert_knowledge_chunks(supabase=supabase, gemini=gemini)

    print("Sync complete.")
    print(f"Tenant: {INSTANCE_ID}")
    print("Prompt fields updated: router_system_prompt, system_prompt_addon, hyde_system_prompt, final_system_prompt, memory_summary_system_prompt")
    print(f"Knowledge chunks inserted: {inserted}")


if __name__ == "__main__":
    asyncio.run(main())
