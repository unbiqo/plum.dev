# Dami Works AI Agent — Мастер-спецификация проекта

> Версия: 1.1 · Дата: 2026-06-24 · Статус: живой документ

---

## Содержание

1. [Product Vision & Business Context](#1-product-vision--business-context)
2. [Обзор архитектуры системы](#2-обзор-архитектуры-системы)
3. [Request Pipeline — детальный разбор](#3-request-pipeline)
4. [Система роутинга](#4-система-роутинга)
5. [Стейт-машина диалога](#5-стейт-машина-диалога)
6. [Roleplay Demo Module](#6-roleplay-demo-module)
7. [Технические требования: Cost / Efficiency](#7-технические-требования-cost--efficiency)
8. [Омниканальность: текущее и роадмап](#8-омниканальность)
9. [Слой данных (Supabase)](#9-слой-данных-supabase)
10. [LLM Generation Pipeline](#10-llm-generation-pipeline)
11. [SaaS / Multi-tenant контракт](#11-saas--multi-tenant-контракт)
12. [Окружение и деплой](#12-окружение-и-деплой)
13. [Известные пробелы и роадмап](#13-известные-пробелы-и-роадмап)

---

## 1. Product Vision & Business Context

### 1.1 Цель продукта и "Вау-эффект"

Dami Works AI Agent — это **флагманский продукт, живое портфолио и главный лидген-инструмент** компании Dami Works одновременно.

Бот продаёт ИИ-разработку самим фактом своего существования. Каждый контакт с потенциальным клиентом (предпринимателем) — это живая демонстрация уровня разработки:

- **Идеальное удержание контекста** — бот помнит всё сказанное клиентом с первого сообщения, продолжает переговоры с нужной точки даже после длинных пауз
- **Скорость ответов** — мгновенный typing indicator, ответ в секунды, без "подождите пока посчитаю"
- **Экспертная отработка возражений** — "дорого", "подумаю", "нам это не нужно" — обрабатываются как опытный B2B-продавец, не как FAQ-бот
- **Живой персонаж** — бот звучит как опытный AI-архитектор, говорит на языке бизнес-результатов, не технического жаргона

**Метрика успеха вау-эффекта:** лид после ролевой игры сам говорит "как сделать такого же для меня?" — это момент конверсии.

### 1.2 Целевая аудитория

**Первичная:** предприниматели малого и среднего бизнеса (SMB), которые:
- Продают через Instagram DM, WhatsApp, Telegram или собственный сайт
- Теряют лиды из-за медленных ответов менеджеров или отсутствия дожима
- Слышали про ИИ, но не понимают, как это работает на практике именно для их бизнеса

**Вторичная:** маркетологи и операционные директора компаний, ищущие инструменты автоматизации воронки продаж.

**Анти-профиль (не наш клиент):** технари, ищущие open-source решения; компании с бюджетом ниже $300 на первый проект.

### 1.3 Целевые платформы (Omnichannel)

| Платформа | Статус | Компонент |
|---|---|---|
| **Telegram** | ✅ Live | `damiworks_tg_bot/bot.py` |
| **Instagram** | 🔜 Roadmap | Webhook adapter (не реализован) |
| **WhatsApp** | 🔜 Roadmap | Webhook adapter (не реализован) |
| **Web-виджет** | 🔜 Roadmap | REST/WebSocket endpoint (не реализован) |

**Архитектурный принцип:** ядро FastAPI (`damiworks-ai-service`) — **channel-agnostic**. Оно не знает, откуда пришёл пользователь. Вся платформо-специфичная логика остаётся в тонком адаптере (бот, webhook), который строит стандартный `ChatRequest` и получает `ChatResponse`. Стейт-машина диалога работает одинаково на всех каналах.

### 1.4 Главный конверсионный флоу

```
Лид заходит в бот (Telegram / Instagram / WhatsApp / Web)
         │
         ▼
[QUALIFICATION] Бот задаёт 1-2 точных вопроса про боль:
  "откуда идут клиенты", "где теряются заявки", "есть ли менеджеры"
         │
         ▼
[DEMO TRIGGER] Бот предлагает /roleplay — тест-драйв прямо сейчас
  "Давай я прямо сейчас покажу, как ИИ будет общаться с твоими клиентами"
         │
         ▼
[CONTEXT GATE] Бот просит контекст бизнеса лида:
  PDF-каталог, скриншот прайса или текстовое описание (60+ слов)
         │
         ▼
[ROLEPLAY ACTIVE] Бот перевоплощается в идеального продавца бизнеса лида.
  Лид тестирует возражения, цены, ситуации — бот отвечает экспертно
         │
         ▼
[WOW момент] Лид убеждается: "это реально работает"
  Бот ведёт себя лучше, чем живой менеджер лида
         │
         ▼
[EXIT ROLEPLAY] Лид сам спрашивает: "Сколько стоит сделать такого?"
  Бот снимает маску: "Маску снял, вернулся в режим архитектора Dami Works"
         │
         ▼
[CLOSE] Бот закрывает на спецификацию и контакт:
  WhatsApp-номер или Telegram username → менеджер пишет в течение часа
  Точная спецификация проекта → от $300
```

---

## 2. Обзор архитектуры системы

### 2.1 Топология сервисов

```
┌─────────────────────────────────────────┐
│            Клиентские каналы            │
│  Telegram │ Instagram │ WhatsApp │ Web  │
└─────┬─────┴─────┬─────┴────┬─────┴──┬──┘
      │           │          │        │
      ▼           ▼          ▼        ▼
┌──────────┐ ┌─────────┐ ┌───────┐ ┌──────┐
│ TG Bot   │ │ IG Hook │ │ WA    │ │ Web  │   ← Тонкие адаптеры
│ bot.py   │ │(roadmap)│ │ Hook  │ │ API  │     (только транспорт)
└────┬─────┘ └────┬────┘ │(rdmp) │ │(rdmp)│
     └────────────┴──────┴───────┴──┘
                       │
                       │  POST /api/v1/chat
                       │  ChatRequest (channel, chat_id, instance_id, message, attachments)
                       ▼
         ┌─────────────────────────┐
         │   damiworks-ai-service       │
         │   FastAPI :8010         │
         │                         │
         │  api.py  ─►  GeminiSvc  │
         │           ─►  SupabaseSvc│
         └────────────┬────────────┘
                      │
              ┌───────┴────────┐
              │                │
              ▼                ▼
         ┌─────────┐    ┌────────────┐
         │ Supabase │    │ Google     │
         │ (state,  │    │ Gemini API │
         │  RAG,    │    │ (LLM)      │
         │  logs)   │    └────────────┘
         └─────────┘
```

### 2.2 Multi-tenant / SaaS

Каждый клиентский проект — отдельный **tenant** с уникальным `instance_id`. Один деплой AI-сервиса обслуживает неограниченное количество тенантов. Конфигурация каждого (системный промпт, коммерческий контекст, список продуктов, база знаний) хранится в Supabase и загружается на лету по `instance_id`.

Собственный Dami Works бот использует `instance_id = "damiworks_dev"` (конфигурируется в `damiworks_tg_bot/.env`).

### 2.3 Channel-agnostic принцип

Стейт-машина, роутинг, диалоговое состояние — всё это работает независимо от канала. Сессия хранится по ключу `(instance_id, channel, chat_id)`. Switching между платформами для одного клиента — отдельные сессии, но `user_memories` могут использоваться кросс-чанально при наличии единого user_id.

---

## 3. Request Pipeline

Полная последовательность шагов для одного входящего сообщения (`POST /api/v1/chat` в `damiworks-ai-service/app/api.py`):

```
 1. Rate-limit check
    └─ Динамический лимит по режиму (sliding window на (channel, chat_id)):
       • B2B-режим (roleplay_demo_active=False): 10 запросов/мин — нормальный темп квалификации
       • Roleplay-режим (roleplay_demo_active=True): 20 запросов/мин — предприниматель активно тестирует
         бота короткими репликами и возражениями, жёсткий лимит убивает вау-эффект
    └─ Переключение происходит в момент установки roleplay_demo_active=True в dialog_state
    └─ Exceeds → HTTP 429 с user-friendly сообщением (не техническим)

 2. Typing indicator
    └─ Async fire-and-forget: send_platform_typing_indicator(platform, user_id)
    └─ Telegram: sendChatAction "typing"
    └─ Instagram: Graph API "typing_on"
    └─ WhatsApp: configurable endpoint

 3. Load tenant settings
    └─ supabase.get_tenant_settings(instance_id)
    └─ Содержит: system_prompt_addon, final_system_prompt, router_system_prompt,
                 hyde_system_prompt, memory_summary_system_prompt, commercial_context

 4. Session reset / expiry
    └─ reset_context=True → clear_conversation_state() (явный сброс)
    └─ Двухуровневая модель таймаутов (целевая архитектура):
       • Roleplay context (roleplay_demo_context_summary и все ROLEPLAY_* ключи):
         сбрасывается при неактивности ≥6 часов — симуляция потеряла актуальность
       • B2B dialog_state (pain_expressed, price_exposed, close_consented, contact_phone_collected):
         живёт 48–72 часа или до явного закрытия сделки — предприниматель может вернуться
         через 8-10 часов, бот обязан помнить прогресс квалификации и не гнать Stage 1 заново
       • Текущее состояние: единый 6-часовой таймаут для всего (SESSION_TIMEOUT в api.py) —
         это технический долг, подлежащий разделению в рамках roadmap

 5. Fetch & merge chat history
    └─ supabase.fetch_recent_chat_history() → logged_history
    └─ Merge с payload.chat_history (клиент может прислать свою историю)
    └─ _strip_generation_fallback_history() убирает деградировавшие ответы

 6. client_facts extraction
    └─ Из session_metadata.client_facts (кеш) или scan до 200 сообщений истории
    └─ Факты: business_niche, crm, lead_volume, target_solution
    └─ Обновляется в session_metadata и сохраняется в Supabase

 7. dialog_state build
    └─ Из session_metadata[DIALOG_STATE_KEY]
    └─ Содержит флаги воронки: pain_expressed, demo_activated, price_exposed,
       close_consented, contact_phone_collected, roleplay_demo_active, ...

 8. Roleplay detection
    └─ _detect_roleplay_demo_context(message, chat_history, dialog_state)
    └─ Возвращает: {active, exit, new_request, topic}

 9. Roleplay context gate (may return early)
    └─ _handle_roleplay_context_gate()
    └─ Если активируется roleplay и нет сохранённого контекста → ждём файл/текст
    └─ Подробнее: раздел 6

10. Deterministic early-exit gates (без LLM)
    └─ /start + reset_context → START_GREETING_ANSWER (hardcoded, no LLM)
    └─ Запрос портфолио/кейсов → DOCUMENTS_SITE_ANSWER (hardcoded, no LLM)
    └─ Явный запрос цены Dami Works → _build_price_override_answer() (hardcoded)

11. Sales stage inference (local heuristic)
    └─ _infer_sales_stage_transition_local() → stage: none/stage_2/stage_3/stage_4
    └─ _infer_content_followup_local() → mechanism_detail / safety_quality_detail / none

12. Route assembly
    └─ Формируем список routes[] на основе stage + roleplay state + intent flags
    └─ roleplay_demo_active → routes = [GENERAL] (блокирует RAG/CHECKOUT)

13. RAG vector search
    └─ Только если RAG_REQUIRED в routes
    └─ HyDE rewrite (опционально): gemini.rewrite_query_hyde() → улучшенный запрос
    └─ get_embedding(query) → supabase.search_knowledge_base(embedding, threshold=0.3)

14. Commercial context load
    └─ Только если CHECKOUT в routes И has_explicit_commercial_intent
    └─ supabase.get_checkout_products() → список ProductCard
    └─ _select_checkout_product() определяет наиболее подходящий продукт

15. LLM generation
    └─ Roleplay path: gemini.answer_roleplay_with_demo_context_json() → {predicted_route, text_response}
    └─ Default path: gemini.answer_with_route_json() → {predicted_route, text_response}
    └─ Fallback на _answer_with_rag_retry() если JSON невалиден или пустой ответ
    └─ Один проход — финальный ответ сразу, без rewrite pass

16. Output filter pipeline (только если NOT roleplay_output_active)
    └─ Подробнее: раздел 7.3

17. Format & spacing
    └─ _format_messenger_answer() — нормализует пробелы и переносы для мессенджеров

18. Persist session state
    └─ _update_dialog_state_after_answer() — обновляем флаги воронки по ответу
    └─ supabase.upsert_chat_session_metadata()

19. Log to chat_logs
    └─ supabase.log_chat(channel, chat_id, instance_id, message, ai_response, routes, metadata)

20. Async memory refresh (background task)
    └─ Если условие refresh: обновляем user_memories через gemini
    └─ Не блокирует ответ клиенту
```

---

## 4. Система роутинга

### 4.1 Пять маршрутов

| Route | Когда применяется | Что происходит |
|---|---|---|
| `GENERAL` | Приветствия, small talk, простые вопросы | Короткий ответ без RAG |
| `RAG_REQUIRED` | Вопросы про AI-агентов, кейсы, интеграции, внедрение | Vector search + LLM answer |
| `CHECKOUT` | Явный запрос цены, покупка, оформление заявки | Загрузка продуктов + коммерческий ответ |
| `ROLEPLAY` | Явный запрос тест-драйва: /roleplay, "отыграй роль продавца" | Roleplay context gate → B2C simulation |
| `EXIT_ROLEPLAY` | Явный выход из ролевой игры | Очистка roleplay state, возврат в B2B режим |

### 4.2 Heuristic-first подход

`_heuristic_routes()` в `gemini_service.py` выполняется первым — чистый Python, без LLM-вызова:

- Соответствие паттернам `/roleplay`, выход из ролевой игры → сразу нужный Route
- Коммерческие паттерны (цена, купить, заказать) → CHECKOUT
- Технические паттерны (агент, CRM, интеграция, воронка) → RAG_REQUIRED
- Всё остальное → GENERAL

**LLM-роутер** включается только когда heuristic вернул чистый `[GENERAL]` — неоднозначные сообщения.

### 4.3 Combined JSON response

Ключевой паттерн экономии токенов: один LLM-вызов возвращает и маршрут, и ответ:

```json
{
  "predicted_route": "GENERAL | ROLEPLAY | EXIT_ROLEPLAY",
  "text_response": "Финальный ответ клиенту на русском"
}
```

Structured output через Gemini `response_mime_type="application/json"` + `response_schema`. Это исключает отдельный classify-вызов для большинства запросов.

### 4.4 Routing contract (обязателен к соблюдению)

Добавление нового Route требует обновления **всех трёх** мест:
1. `Route` enum в `schemas.py`
2. `_heuristic_routes()` в `gemini_service.py`
3. `_parse_routes()` в `gemini_service.py`
4. `ROUTER_SYSTEM_PROMPT` в `gemini_service.py`

---

## 5. Стейт-машина диалога

### 5.1 Схема dialog_state

`dialog_state` — словарь, хранящийся как JSONB в `chat_sessions.metadata[dialog_state]`. Обновляется при каждом запросе.

**Флаги воронки (BUYING_MILESTONE_KEYS):**

| Ключ | Тип | Значение |
|---|---|---|
| `pain_expressed` | bool | Лид выразил боль в продажах |
| `demo_activated` | bool | Тест-драйв (/roleplay) запущен |
| `price_exposed` | bool | Цена Dami Works уже показана |
| `close_consented` | bool | Лид согласился на расчёт/оформление |
| `contact_phone_collected` | bool | Телефон/контакт получен и верифицирован |

**Roleplay флаги:**

| Ключ | Тип | Значение |
|---|---|---|
| `roleplay_demo_active` | bool | Roleplay сейчас активен |
| `roleplay_demo_topic` | str | Тема/ниша текущей симуляции |
| `roleplay_demo_awaiting_context` | bool | Ждём файл/текст от лида |
| `roleplay_demo_context_summary` | str | Извлечённый текст из файла (≤5000 chars) |
| `roleplay_demo_context_source` | str | Источник: "text_description" / filename |
| `roleplay_demo_context_wait_count` | int | Сколько раз просили файл (авто-старт при ≥2) |
| `roleplay_demo_no_file_fallback` | bool | Старт без файла (общие знания) |

**Коммерческие флаги:**

| Ключ | Тип | Значение |
|---|---|---|
| `automation_goal` | str | Что хочет автоматизировать клиент |
| `service_focus` | str | base / cart / agent |
| `selected_product_id` | str | ID выбранного продукта из `products` |

### 5.2 Продажные стадии (Sales Stages)

```
Stage 1 — Qualification
  ├── Узнаём: нишу, канал заявок, CRM/сайт, узкое место
  ├── Разрешено: любые консультативные вопросы
  └── Запрещено: называть цены, показывать продуктовые карточки

Stage 2 — Consultation & Comparison (trigger: pain_expressed + согласие смотреть варианты)
  ├── Сравниваем: Базовый ИИ-ассистент / Авто-корзина / ИИ-агент под ключ
  ├── Разрешено: описание пакетов, бизнес-ценность
  └── Запрещено: конкретные цены, product card, checkout

Stage 3 — Price Presentation (trigger: согласие после Stage 2)
  ├── Называем цены из dynamic product context
  ├── Разрешено: ценовые ориентиры, scope of work
  └── Запрещено: CREATE_CART, product card

Stage 4 — Checkout (trigger: явное согласие после Stage 3)
  ├── Backend генерирует product card / cart / handoff
  ├── Разрешено: всё коммерческое закрытие
  └── Принцип: один аффирмативный ответ = одна стадия вперёд
```

### 5.3 Override-инструкции по стадии

`_format_buying_readiness_instruction(dialog_state)` возвращает текстовую инструкцию, которая инжектируется в `response_instruction` перед системным промптом. Например, если `close_consented=True`, инструкция запрещает спрашивать про источник трафика и форсирует закрытие на спецификацию.

---

## 6. Roleplay Demo Module

### 6.1 Триггеры активации

Явные команды (`_is_explicit_roleplay_command()`):
- `/roleplay` (команда Telegram)
- "отыграй роль продавца", "сыграй роль", "будь продавцом"
- "представь, что ты менеджер", "включи режим продавца"
- "я твой клиент... погнали / поехали / начинаем"
- "в роли клиента", "пишу как клиент"

Имплицитные (через LLM-роутер → ROLEPLAY route) — неоднозначные запросы на симуляцию.

### 6.2 Context Gate — три режима

После активации бот переходит в режим ожидания вводных (`roleplay_demo_awaiting_context=True`):

```
Context Gate
     │
     ├── [File mode] Пришёл PDF/image/doc?
     │      └─ extract_roleplay_context_from_attachment()
     │         → multimodal LLM разбирает файл
     │         → строковый summary ≤5000 chars → session_metadata
     │         → roleplay_demo_active=True, далее работаем со строкой
     │
     ├── [Text mode] Сообщение ≥60 chars с бизнес-терминами?
     │      └─ extract_roleplay_context_from_text()
     │         → LLM структурирует описание в fact-sheet
     │         → строковый summary → session_metadata
     │
     ├── [No-file fallback] "без файла" / wait_count ≥ 2?
     │      └─ roleplay_demo_active=True, context_summary=""
     │         Демо на общих знаниях, бот предупреждает о приблизительности
     │
     └── [Wait] Иначе → wait_count++, повторный запрос файла/текста
```

### 6.3 Однократный парсинг медиафайлов (токен-эффективность)

**Правило:** файл отправляется в Gemini **один раз** при загрузке.

Результат сохраняется как `roleplay_demo_context_summary` (plain text, ≤5000 символов) в `chat_sessions.metadata`. Все последующие сообщения внутри ролевой игры используют только **строковый контекст** — бинарный файл не переотправляется.

Это критично для экономии: мультимодальные токены (PDF/image) в несколько раз дороже текстовых. Без этого механизма ролевая игра из 10 сообщений = 10 мультимодальных вызовов.

### 6.4 Изоляция B2B / B2C контекстов

**Жёсткое разделение:**

| Аспект | B2B режим (Dami Works) | B2C roleplay (симуляция) |
|---|---|---|
| Системный промпт | 13-слойный guard stack | Только `ROLEPLAY_DEMO_SYSTEM_PROMPT` |
| RAG | Supabase knowledge_base | Запрещён |
| Коммерческий контекст | Dami Works products | Запрещён |
| Цены | Из products table | Только из demo_context |
| CTA | WhatsApp, спецификация, $300 | Вопрос-хук продавца в нише |
| Output filters | Все активны | Все отключены (`roleplay_output_active=True`) |

**Гарантия изоляции:** `demo_context` передаётся как временная инструкция в промпте, явно помеченная "session-local". Она никогда не пишется в `knowledge_base` или `tenants`. При вызове `_clear_roleplay_state()` все ROLEPLAY_* ключи удаляются из dialog_state.

**Запрет утечки Dami Works данных в roleplay** (ROLEPLAY_DEMO_SYSTEM_PROMPT):
- `$300`, "проект", "спецификация", "WhatsApp", "Dami Works" — запрещены в ответе
- "Задача ясна", "Фиксируем в спецификации" — запрещены (prompt leakage)
- Заключительный вопрос принадлежит только симулируемому бизнесу

**Запрет утечки roleplay данных в B2B** (Output filters):
- `_cleanup_damiworks_cta_from_roleplay_answer()` — убирает Dami Works CTA если они просочились
- `_repair_forbidden_roleplay_gate_answer()` — убирает служебные фразы context gate

### 6.5 Выход из ролевой игры

Триггеры выхода (`_is_roleplay_demo_exit_request()`):
- "выйди из роли", "сними маску", "хватит играть"
- "вернись к Dami Works", "я про ИИ-агента"
- "сколько стоит сделать такого бота" (коммерческий intent во время roleplay)

При выходе:
1. `_clear_roleplay_state()` — удаляет все ROLEPLAY_* ключи
2. Bridge instruction: `"Маску снял, вернулся в режим архитектора Dami Works."`
3. Бот использует roleplay как живой пример при расчёте стоимости ("такой бот для вашего бизнеса")

---

## 7. Технические требования: Cost / Efficiency

### 7.1 Изоляция контекстов (hard requirement)

- `roleplay_demo_context_summary` — session-scoped, максимум 5000 символов
- Никогда не пишется в `knowledge_base`, `tenants`, `user_memories`
- `_format_roleplay_file_context_instruction()` явно помечает контекст как "session-local"
- Все данные симуляции (цены детейлинга, состав пиццы и т.д.) уничтожаются при EXIT_ROLEPLAY
- Механизм заморозки: `_clear_roleplay_state()` делает `pop()` на все ROLEPLAY_* ключи

### 7.2 Экономия токенов

**Однократный парсинг медиа** (см. раздел 6.3):
- Файл → multimodal LLM → строка → Supabase session
- Стоимость последующих roleplay-сообщений = только текстовые токены

**Combined JSON response** (раздел 4.3):
- Один LLM-вызов = маршрут + ответ
- Экономия: устраняет отдельный classify-вызов

**Ограничение output:**
- `ECONOMY_MAX_OUTPUT_TOKENS = 384` для большинства ответов — достаточно для B2B режима
- Roleplay: разный лимит по сложности запроса:
  - Стандартный roleplay (одно возражение / один вопрос) → 40-50 слов, B2C Instagram формат
  - Сложный контекст (комплексный вопрос с несколькими позициями, расчётом и датами) → до
    100-120 слов, бюджет в 384 токена это покрывает
  - Искусственное жёсткое ограничение длины в системном промпте ролевки ("max 40-50 words")
    нужно смягчить: модель сама выберет нужную длину исходя из задачи, инструкция задаёт стиль
    (кратко, живо, один аргумент + вопрос), а не жёсткий счётчик слов

**Детерминированные early exits** (раздел 3, шаг 10):
- Приветствие, портфолио-запрос, явная цена Dami Works → ответ без LLM
- Экономия: ~15-20% запросов обрабатываются без обращения к Gemini

**Heuristic-first роутинг:**
- Большинство роутинг-решений — чистый Python regex
- LLM-роутер вызывается только для неоднозначных сообщений

### 7.3 Output Filter Pipeline

Применяются **только** когда `not roleplay_output_active` (вне ролевой игры).

Порядок применения в `api.py`:

| Функция | Назначение |
|---|---|
| `_checkout_contact_guard_answer()` | Блокирует "заявка принята" без реального телефона в сообщении |
| `_repair_which_option_better_answer()` | Исправляет ответы на "какой вариант лучше?" |
| `_repair_stage_3_price_answer()` | Контролирует корректность ценового этапа |
| `_build_acknowledgement_continuation_answer()` | Обрабатывает однословные подтверждения |
| `_sanitize_roleplay_output()` | Применяется при roleplay_output_active — убирает спецсимволы |
| `_cleanup_damiworks_cta_from_roleplay_answer()` | Убирает Dami Works CTA просочившиеся из roleplay |
| `_remove_forbidden_traffic_question_after_milestone()` | Запрет спрашивать про трафик после milestone |
| `_repair_completed_function_qualification_answer()` | Убирает преждевременные "задача выполнена" |
| `_repair_forbidden_roleplay_gate_answer()` | Убирает служебные фразы context gate |
| `_cleanup_contact_cta_after_phone_collected()` | Запрет просить телефон повторно |
| `_sanitize_prompt_leakage_answer()` | Убирает prompt artifacts (глобально) |
| `_ensure_sales_initiative_answer()` | Бот не заканчивает тупиком |
| `_final_contact_confirmation_answer()` | Финальное подтверждение если телефон уже есть |

**Ключевое правило:** ни один фильтр не имеет права модифицировать ответ если `roleplay_output_active=True`. Проверка выполняется на уровне `api.py` до вызова каждого фильтра.

### 7.4 Интеллектуальный захват контактов (model-native)

**Текущая проблема:** Python-хэурестики с regex и словарями числительных (`_RU_HUNDREDS`, `_RU_TENS`, etc.) хрупкие и не покрывают все языковые варианты ("семьсот два ноль", "семьсот двадцать...", смешанный формат с тире и пробелами).

**Целевая архитектура:**

Распознавание телефона делегируется модели через **structured JSON output**:

```json
{
  "predicted_route": "GENERAL",
  "text_response": "Отлично, номер записал. Менеджер напишет вам в WhatsApp...",
  "contact_detected": {
    "phone": "+79201234567",
    "confidence": "high"
  }
}
```

Или через **function calling / tool use**:

```python
# Tool definition
extract_contact_tool = {
    "name": "extract_contact",
    "description": "Extract phone number from user message, including text-written numbers",
    "parameters": {
        "phone_normalized": "string",  # E.164 format or null
        "source_text": "string"         # original fragment
    }
}
```

**Логика бэкенда:**
1. Если в ответе модели `contact_detected.phone` не null → `contact_phone_collected=True`
2. Сохраняем нормализованный номер в `client_facts.phone`
3. Вызываем `_final_contact_confirmation_answer()`
4. Больше не спрашиваем контакт (`_cleanup_contact_cta_after_phone_collected()` пока нужен как fallback)

**Преимущества:** покрывает "плюс семь девятьсот...", "+7 (920) 123-45-67", "89201234567", смешанные форматы без поддержки отдельного парсера.

---

## 8. Омниканальность

### 8.1 Текущее состояние

`ChatRequest.channel` — Literal enum: `"telegram" | "whatsapp" | "instagram" | "web_site"`

API-ядро уже channel-agnostic. Вся дифференциация — в адаптерах.

### 8.2 Typing indicators (реализованы для всех каналов)

`send_platform_typing_indicator()` в `api.py` — async, fire-and-forget:

| Платформа | Механизм | Env var |
|---|---|---|
| Telegram | `sendChatAction` (form-urlencoded) | `TELEGRAM_BOT_TOKEN` / `BOT_TOKEN` |
| Instagram | Meta Graph API `typing_on` (JSON) | `META_PAGE_ACCESS_TOKEN` |
| WhatsApp | Configurable provider endpoint (JSON) | `WHATSAPP_TYPING_ENDPOINT` + `WHATSAPP_ACCESS_TOKEN` |

### 8.3 Roadmap адаптеры

Каждый новый канал — отдельный тонкий сервис, который:
1. Принимает входящее событие (webhook / long-poll)
2. Скачивает вложения, конвертирует в base64
3. Строит стандартный `ChatRequest`
4. POSTит на `/api/v1/chat`
5. Отправляет `ChatResponse.answer` обратно в канал

**Instagram adapter:** Meta Webhooks, верификация `X-Hub-Signature-256`, `messages` event type

**WhatsApp adapter:** Meta Business API webhooks или 360dialog / WATI — зависит от провайдера

**Web widget:** WebSocket или SSE endpoint, фронтенд на React/Vue, режим `channel="web_site"`

### 8.4 Session isolation по каналу

Сессии изолированы по ключу `(instance_id, channel, chat_id)`. Клиент, написавший в Telegram и Instagram — две разные сессии с независимым dialog_state. Это предотвращает утечку контекста между каналами.

---

## 9. Слой данных (Supabase)

### 9.1 Таблицы

| Таблица | Назначение | Ключевые поля |
|---|---|---|
| `tenants` | Конфиг инстанса: промпты, настройки | `instance_id`, `final_system_prompt`, `system_prompt_addon`, `router_system_prompt`, `hyde_system_prompt`, `memory_summary_system_prompt`, `commercial_context` |
| `knowledge_base` | RAG-чанки (vector-indexed) | `instance_id`, `content`, `embedding` (pgvector), `metadata` |
| `chat_logs` | История сообщений | `instance_id`, `channel`, `chat_id`, `role`, `content`, `routes`, `metadata`, `created_at` |
| `chat_sessions` | Session metadata + dialog_state | `instance_id`, `channel`, `chat_id`, `metadata` (JSONB) |
| `user_memories` | Long-term B2B memory summaries | `instance_id`, `channel`, `chat_id`, `memory_text`, `updated_at` |
| `products` | Каталог продуктов для checkout | `product_id`, `title`, `price_tenge`, `currency`, `image_url`, `instance_id` |

### 9.2 Схема dialog_state (JSONB в chat_sessions.metadata)

```json
{
  "dialog_state": {
    "pain_expressed": false,
    "demo_activated": false,
    "price_exposed": false,
    "close_consented": false,
    "contact_phone_collected": false,
    "automation_goal": null,
    "service_focus": null,
    "selected_product_id": null,
    "roleplay_demo_active": false,
    "roleplay_demo_topic": null,
    "roleplay_demo_awaiting_context": false,
    "roleplay_demo_context_summary": null,
    "roleplay_demo_context_source": null,
    "roleplay_demo_context_wait_count": 0,
    "roleplay_demo_no_file_fallback": false
  },
  "client_facts": {
    "business_niche": null,
    "crm": null,
    "lead_volume": null,
    "target_solution": null,
    "phone": null
  }
}
```

### 9.3 RAG vector search

Функция `vector_search` в Supabase (PostgreSQL RPC, определена в `damiworks-ai-service/sql/vector_search.sql`):
- Принимает: embedding vector, instance_id, threshold, match_count
- Возвращает: отранжированные чанки knowledge_base

Embeddings генерируются через `gemini.get_embedding()` → `text-embedding-004` (или аналог).

---

## 10. LLM Generation Pipeline

### 10.1 Гибкая маршрутизация моделей

Все назначения моделей — через `Settings` (конфигурация / env), никогда не хардкодятся в логике сервиса:

| Тип задачи | Рекомендуемая модель | Settings key |
|---|---|---|
| Роутинг, HyDE rewrite, sales-stage classify | `gemini-3.1-flash-lite` | `router_model` |
| RAG_REQUIRED, CHECKOUT ответы | `gemini-3.1-flash-lite` (default) | `rag_model` |
| GENERAL ответы | `gemini-3.1-flash-lite` | `general_model` |
| Roleplay demo | `gemini-2.5-flash` (full) — повышенное качество B2C симуляции | `general_model` (отдельный pool) |
| Embeddings | `text-embedding-004` | `embedding_model` |

Каждая модель имеет опциональный `_pool` вариант для load balancing между несколькими ключами через `GeminiQuotaManager`.

**Принцип:** flash-lite для быстрых/дешёвых операций, full flash для критически важного качества (roleplay — главный конверсионный момент).

### 10.2 Guard prompt stack (B2B режим)

Система промптов собирается последовательно в `answer_with_rag()` / `answer_with_route_json()`:

```
SALES_MASTER_PROMPT           ← "Ты сильный AI-архитектор и продавец, не FAQ-бот"
FINAL_SYSTEM_PROMPT           ← Основные правила ответа, RAG/commercial usage
COMMERCIAL_GUARD_PROMPT       ← Ценовая дисциплина, стадийное продвижение
STYLE_GUARD_PROMPT            ← Лаконичность, бизнес-язык, без жаргона
MESSENGER_FORMAT_GUARD_PROMPT ← Макс 2 предложения в абзаце, \n\n между блоками
PROMPT_LEAKAGE_GUARD_PROMPT   ← Запрет копировать технические инструкции клиенту
CONTEXT_RELEVANCE_GUARD_PROMPT ← Использовать факты только по контексту
FLOW_FLEXIBILITY_GUARD_PROMPT ← Нет жёсткого скрипта, один вопрос за раз
ENGAGEMENT_GUARD_PROMPT       ← Каждый ответ продвигает к следующему шагу
CHECKOUT_CONTACT_VALIDATION_PROMPT ← Не "заявка принята" без реального телефона
CLIENT_FACING_PRIVACY_PROMPT  ← Запрет называть RAG, prompt, backend клиенту
UNIFIED_COMMERCIAL_RULES_PROMPT ← 7 блоков: результат, ценообразование, scope...
OTHER_PLATFORM_GUARD_PROMPT   ← Честный отказ про чужие платформы
```

Дополнительно к стеку добавляются:
- `CRITICAL_COMMERCIAL_TRIGGER_RULE` — гибкость в диалоге, нет анкеты
- `NO_REPEAT_RULE` — запрет повторов
- `response_instruction` (per-turn override из `_format_buying_readiness_instruction()` и других)
- Tenant-specific addon из `tenants.system_prompt_addon`

### 10.3 Roleplay режим (упрощённый стек)

Весь 13-слойный стек заменяется одним промптом:

```
ROLEPLAY_DEMO_SYSTEM_PROMPT   ← B2C продавец, изоляция, финансовая дисциплина,
                                 messenger формат (40-50 слов), запрет Dami Works
+ demo_context (plain text, session-local)
+ response_instruction (roleplay topic + инструкция)
```

### 10.4 Однопроходная генерация (cost target)

**Принцип:** один LLM-вызов → финальный клиентский ответ.

Текущий `_rewrite_sales_answer()` (второй проход) подлежит **упразднению**. Его правила переносятся в усиленный первичный системный промпт:
- Запрет техжаргона → уже в STYLE_GUARD + SALES_MASTER_PROMPT
- Humanize dry RAG language → SALES_REWRITE rules интегрируются в FINAL_SYSTEM_PROMPT
- Destroy repetitive scripts → уже в NO_REPEAT_RULE + ENGAGEMENT_GUARD

**Постобработка остаётся** (pure string manipulation, без LLM):
- `_avoid_repeated_closing_phrase()` — дедупликация закрывающих вопросов
- `_remove_repeated_commercial_closing_question()` — убирает повторяющиеся коммерческие вопросы
- `_soften_absolute_sales_guarantees()` — "гарантированно" → "как правило"
- `_ensure_followup_question_spacing()` — \n\n перед вопросом

**Экономия:** устранение rewrite pass = -50% LLM-вызовов на RAG/CHECKOUT путях.

### 10.5 Retry логика

```
Attempt 1: normal history + full RAG context
Attempt 2: cleaned history (без fallback-ответов) + full RAG context
Attempt 3: cleaned history + пустой RAG/memory context
```

На каждом уровне: tenacity retry для 503/UNAVAILABLE ошибок Gemini.

### 10.6 GeminiQuotaManager

- Отслеживает RPM/TPM/RPD по каждому API ключу
- При исчерпании ключа — ротация на следующий
- При исчерпании всех ключей → `GeminiQuotaExhausted` → fallback answer или error response
- `estimate_tokens()` для предварительной оценки стоимости запроса

---

## 11. SaaS / Multi-tenant контракт

**Это жёсткое архитектурное правило, нарушение которого ломает масштабирование:**

| Что нужно изменить | Правильное место | Запрещённое место |
|---|---|---|
| Текст ответов бота | `tenants.final_system_prompt` в Supabase | Python-код |
| Цены и продукты | `products` таблица в Supabase | Python-код |
| База знаний / факты | `knowledge_base` чанки в Supabase | Python-код |
| Скрипты продаж | `tenants.system_prompt_addon` | Python-код |
| Добавить нового клиента | Новая строка в `tenants` + populate `knowledge_base` + `products` | Fork сервиса |

**Исключения (допустимо в коде):**
- Детерминированные hardcoded ответы (greeting, portfolio redirect) — они одинаковы для всех тенантов
- Системные сообщения об ошибках (rate limit, service unavailable)

---

## 12. Окружение и деплой

### 12.1 Переменные окружения

**`damiworks-ai-service/.env`:**
```
GEMINI_API_KEY=...                    # Primary key (обязателен)
GEMINI_API_KEY_2=...                  # Дополнительные ключи для rotation (опционально)
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
TELEGRAM_BOT_TOKEN=...                # Для typing indicator из AI service (опционально)
META_PAGE_ACCESS_TOKEN=...            # Instagram typing indicator (опционально)
INSTAGRAM_MESSAGES_ENDPOINT=...      # Default: https://graph.facebook.com/v19.0/me/messages
WHATSAPP_TYPING_ENDPOINT=...         # WhatsApp typing indicator endpoint (опционально)
WHATSAPP_ACCESS_TOKEN=...            # WhatsApp auth (опционально)
ENABLE_GENERATION_FALLBACK=false     # Включить детерминированные fallback-ответы при ошибке LLM
```

**`damiworks_tg_bot/.env`:**
```
BOT_TOKEN=...
AI_SERVICE_URL=http://127.0.0.1:8010/api/v1/chat
INSTANCE_ID=damiworks_dev
```

### 12.2 Локальный запуск

**AI service (port 8010):**
```powershell
cd damiworks-ai-service
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

**Telegram bot:**
```powershell
cd damiworks_tg_bot
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py
```

**Синтаксическая проверка после правок:**
```powershell
python -m py_compile damiworks-ai-service/app/gemini_service.py
python -m py_compile damiworks-ai-service/app/api.py
```

### 12.3 Утилиты

| Скрипт | Назначение |
|---|---|
| `damiworks-ai-service/scripts/load_rag_documents.py` | Bulk-загрузка RAG чанков в Supabase |
| `damiworks-ai-service/scripts/index_vector_knowledge_base.py` | Генерация embeddings и индексация |
| `damiworks-ai-service/scripts/update_final_system_prompt.py` | Обновление системного промпта тенанта |
| `damiworks-ai-service/sql/vector_search.sql` | SQL для RPC функции поиска (применять в Supabase SQL editor) |

---

## 13. Известные пробелы и роадмап

### Критические (блокируют omnichannel)

- [ ] **Instagram webhook adapter** — приём DM через Meta Webhooks, отправка ответов
- [ ] **WhatsApp webhook adapter** — Meta Business API или 360dialog/WATI провайдер
- [ ] **Web widget** — React/Vue компонент + WebSocket/SSE endpoint в FastAPI

### Высокий приоритет (улучшение качества)

- [ ] **Model-native phone extraction** — замена regex/словарей на structured JSON output (раздел 7.4)
- [ ] **Single-pass generation** — устранение `_rewrite_sales_answer()`, интеграция правил в primary prompt (раздел 10.4)
- [ ] **Roleplay model upgrade** — выделенная конфигурация для `general_model` в roleplay с полным flash (раздел 10.1)
- [ ] **Двухуровневые таймауты сессии** — разделить `SESSION_TIMEOUT`: roleplay context 6h, B2B dialog_state 48-72h; рефакторинг `_is_new_session()` и `get_chat_session_metadata()` (раздел 3, пункт 4)
- [ ] **Динамический rate-limit** — проверять `dialog_state.roleplay_demo_active` перед rate-limit check, переключать bucket с 10 на 20 req/min (раздел 3, пункт 1)
- [ ] **Roleplay output length** — убрать жёсткий "max 40-50 words" из `ROLEPLAY_DEMO_SYSTEM_PROMPT`, заменить на принцип "кратко исходя из сложности" (раздел 7.2)

### Средний приоритет (операционная зрелость)

- [ ] **Admin панель** — управление knowledge_base чанками без SQL Editor
- [ ] **Analytics dashboard** — конверсия по стадиям воронки, время до конверсии, топ болей
- [ ] **A/B тестирование промптов** — версионирование `final_system_prompt` с метриками
- [ ] **Cross-channel memory** — объединение `user_memories` для одного клиента с разных каналов

### Низкий приоритет (nice to have)

- [ ] **Голосовые сообщения** — STT → text → стандартный pipeline
- [ ] **Inline кнопки** — Telegram InlineKeyboard для выбора пакета/стадии
- [ ] **Webhook retry queue** — надёжная очередь для нестабильных WhatsApp/Instagram соединений
- [ ] **Monitoring / alerting** — Sentry + Grafana для quota exhaustion, error rate, latency

---

*Документ отражает состояние кодовой базы на 2026-06-24. При изменении архитектуры обновлять синхронно с кодом.*
