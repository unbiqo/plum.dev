from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
AI_SERVICE_DIR = PROJECT_ROOT / "plum-ai-service"
INSTANCE_ID = "plum_dev"

sys.path.insert(0, str(AI_SERVICE_DIR))

from app.config import get_settings  # noqa: E402
from app.gemini_service import GeminiService  # noqa: E402
from app.supabase_service import SupabaseService  # noqa: E402


COMPANY_NAME = "Plum Dev"

COMMERCIAL_CONTEXT = (
    "Разработка кастомных ИИ-агентов, умных воронкок продаж и авто-корзин "
    "для мессенджеров (Instagram, Telegram). Базовый ассистент (FAQ + сбор "
    "контактов) — от $300. Авто-корзина под ключ (с интеграцией в CRM/Google "
    "Таблицы) — от $600. Сроки: от 7 до 14 дней. Работаем по договору, оплата "
    "по брифу/инвойсу. Точная смета — только после аудита на созвоне."
)

ROUTER_SYSTEM_PROMPT = (
    "Ты — классификатор сообщений для ИИ-агентства Plum Dev. Твоя задача — "
    "строго определить маршруты. GENERAL: приветствия, обобщенный small talk. "
    "RAG_REQUIRED: технические вопросы, стек, интеграции с CRM (amoCRM, "
    "Битрикс24), кейсы, портфолио, как ИИ заменяет людей. CHECKOUT: запросы "
    "точной цены, стоимости, готовность заказать, созвониться, заполнить бриф "
    "или пройти аудит."
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

ПРАВИЛО СВОЕВРЕМЕННОГО ПРЕДЛОЖЕНИЯ:
Переходи к тестовому боту, аудиту или созвону только когда выполнены два условия:
1. Ты выяснил, как устроены продажи у клиента прямо сейчас: где собирает заявки, сколько людей в команде, где теряются клиенты.
2. Ты полностью закрыл текущее сомнение или возражение клиента.
До этого отвечай по сути и задавай один точечный вопрос про бизнес."""

KNOWLEDGE_CHUNKS = [
    (
        "Опыт и стек Plum Dev. Мы пишем ИИ-системы на Python и подключаем "
        "передовые языковые модели, включая Gemini и OpenAI. Для точных ответов "
        "по регламентам компании подключаем базы знаний RAG: агент отвечает не "
        "из общих догадок, а по загруженным правилам, документам, FAQ и условиям бизнеса."
    ),
    (
        "Интеграции Plum Dev. Мы связываем ИИ-агентов с CRM-системами и рабочими "
        "таблицами: amoCRM, Битрикс24, Google Таблицы, Excel и внутренние API. "
        "Агент может отправлять уведомления в Telegram-каналы, создавать строки "
        "в таблицах и передавать менеджеру готовую карточку клиента в реальном времени."
    ),
    (
        "Авто-корзины Plum Dev. ИИ умеет не просто отвечать, а вести клиента по "
        "воронке: выявлять потребность, предлагать подходящий тариф или продукт, "
        "собирать ФИО, телефон, город и формировать готовую заявку для менеджера. "
        "Такой сценарий особенно полезен для Instagram, Telegram и других мессенджеров."
    ),
    (
        "Безопасность Plum Dev. Данные переписок, коммерческие промпты и настройки "
        "тенантов изолированы. Доступы к CRM и таблицам подключаются через защищенные "
        "API-ключи и сервисные токены. Клиентские данные не используются для публичного "
        "обучения моделей и не смешиваются между проектами."
    ),
    (
        "Коммерческие условия Plum Dev. Базовый ассистент с FAQ и сбором контактов "
        "стартует от $300. Авто-корзина под ключ с интеграцией в CRM или Google "
        "Таблицы стартует от $600. Обычно запуск занимает от 7 до 14 дней, но точная "
        "смета и срок фиксируются только после аудита воронки и короткого созвона."
    ),
    (
        "Возражение про менеджеров и гарантии. Plum Dev не обещает, что ИИ будет "
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


def upsert_tenant(supabase: SupabaseService) -> None:
    print(f"[1/3] Upserting tenant: {INSTANCE_ID}")
    supabase.client.table("tenants").upsert(
        {
            "instance_id": INSTANCE_ID,
            "company_name": COMPANY_NAME,
            "commercial_context": COMMERCIAL_CONTEXT,
            "router_system_prompt": ROUTER_SYSTEM_PROMPT,
            "final_system_prompt": FINAL_SYSTEM_PROMPT,
        },
        on_conflict="instance_id",
    ).execute()
    print("[OK] Tenant upserted")


def clear_existing_knowledge(supabase: SupabaseService) -> None:
    print(f"[2/3] Clearing existing knowledge_base chunks for {INSTANCE_ID}")
    supabase.client.table("knowledge_base").delete().eq(
        "instance_id",
        INSTANCE_ID,
    ).execute()
    print("[OK] Existing chunks cleared")


async def seed_knowledge_base(
    *,
    supabase: SupabaseService,
    gemini: GeminiService,
) -> None:
    print(f"[3/3] Embedding and inserting {len(KNOWLEDGE_CHUNKS)} knowledge chunks")

    inserted = 0
    for index, chunk in enumerate(KNOWLEDGE_CHUNKS, start=1):
        content = f"Title: Plum Dev knowledge chunk {index}\n\n{chunk}"
        print(f"  - Embedding chunk {index}/{len(KNOWLEDGE_CHUNKS)}...")
        embedding = await gemini.get_embedding(content)
        supabase.client.table("knowledge_base").insert(
            {
                "instance_id": INSTANCE_ID,
                "content": content,
                "embedding": embedding,
            }
        ).execute()
        inserted += 1
        print(f"    [OK] Inserted chunk {index}")

    print(f"[OK] Knowledge base seeded. Inserted chunks: {inserted}")


async def main() -> None:
    load_environment()
    settings = get_settings()
    supabase = SupabaseService(settings)
    gemini = GeminiService(settings)

    print("Seeding Supabase data for Plum Dev")
    print(f"Instance ID: {INSTANCE_ID}")
    upsert_tenant(supabase)
    clear_existing_knowledge(supabase)
    await seed_knowledge_base(supabase=supabase, gemini=gemini)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
