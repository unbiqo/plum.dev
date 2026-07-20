# Dami Works AI Agent — Мастер-спецификация проекта

> Версия: 1.2 · Дата: 2026-06-25 · Статус: целевая архитектура / replacement spec  
> Этот документ заменяет `project_specs.md` v1.1 как основной источник контекста для Opus.  
> Главная цель версии 1.2: перестроить Dami Works из roleplay-first бота в Adaptive Sales Intelligence систему, которая сама выбирает правильную глубину общения, wow-механизм и next best action под конкретного клиента.

> **Статус реализации (Phases 1–9 завершены):** слой `sales_intelligence` реализован и подключён
> в `api.py`. Актуальное состояние кода (pipeline, output-filter audit, что enabled/legacy)
> задокументировано в [`docs/adaptive_sales_intelligence_v2.md`](docs/adaptive_sales_intelligence_v2.md).
> Этот файл остаётся целевой спецификацией (intent); doc — снимок реализации. Не сделано:
> LLM-extractor (canon Phase 3), prompt-режим `roleplay_demo` (намеренно legacy).

---

## Содержание

1. [Product Vision & Business Context](#1-product-vision--business-context)
2. [Ключевой архитектурный сдвиг v1.2](#2-ключевой-архитектурный-сдвиг-v12)
3. [Conversation Modes](#3-conversation-modes)
4. [Wow Mechanism Router](#4-wow-mechanism-router)
5. [Целевая архитектура системы](#5-целевая-архитектура-системы)
6. [Целевая структура проекта](#6-целевая-структура-проекта)
7. [Request Pipeline v1.2](#7-request-pipeline-v12)
8. [Session Metadata v1.2](#8-session-metadata-v12)
9. [Sales Intelligence Layer](#9-sales-intelligence-layer)
10. [Structured Extraction](#10-structured-extraction)
11. [Conversation Strategy Engine](#11-conversation-strategy-engine)
12. [ROI Engine](#12-roi-engine)
13. [Roleplay Demo Module](#13-roleplay-demo-module)
14. [Routing System](#14-routing-system)
15. [Prompt Composer & LLM Generation](#15-prompt-composer--llm-generation)
16. [Commercial / Price Handling Policy](#16-commercial--price-handling-policy)
17. [Data Layer / Supabase](#17-data-layer--supabase)
18. [Cost / Efficiency Requirements](#18-cost--efficiency-requirements)
19. [Testing Requirements](#19-testing-requirements)
20. [Migration Plan](#20-migration-plan)
21. [Implementation Rules for Opus](#21-implementation-rules-for-opus)

---

## 1. Product Vision & Business Context

### 1.1 Суть Dami Works

Dami Works продает не обычных чат-ботов и не кнопочные автоответчики. Dami Works создает AI-сотрудников нового поколения: AI-агентов, которые заменяют или усиливают продажи, поддержку, квалификацию лидов, follow-up и операционные процессы бизнеса.

Главная задача Dami Works AI Agent — быть одновременно:

1. лидген-инструментом Dami Works;
2. живым портфолио качества разработки;
3. AI-продавцом, который квалифицирует клиентов;
4. демонстрацией того, что такой же AI-сотрудник может работать в бизнесе клиента.

### 1.2 Главный принцип продаж

Бот не должен продавать через анкету. Бот должен продавать через уместный wow-эффект.

Для разных клиентов wow-эффект разный:

- микробизнесу важно увидеть простоту, заботу, экономию времени и отсутствие потерянных диалогов;
- зрелому SMB важно увидеть цифры, ROI, контроль воронки и потери из-за человеческого фактора;
- integration-heavy клиенту важно увидеть, что Dami Works умеет связывать AI с CRM, складом, таблицами, календарем, оплатой и внутренними процессами;
- cold lead нужно сначала простое объяснение, а не вопросы про маржу и CRM;
- low-fit клиенту нельзя выдумывать окупаемость — его нужно мягко прогреть или честно объяснить, когда AI станет актуален.

### 1.3 Целевая аудитория

**Primary ICP:** предприниматели и SMB, которые:

- получают входящие заявки через WhatsApp, Instagram DM, Telegram, сайт, формы, маркетплейсы или CRM;
- теряют лиды из-за медленных ответов, отсутствия 24/7, забытых follow-up или слабой квалификации;
- используют менеджеров, владельца или хаотичные процессы для обработки заявок;
- хотят увеличить конверсию, снять рутину или связать AI с внутренними системами.

**Secondary ICP:** маркетологи, операционные директора, руководители продаж и владельцы с более зрелой инфраструктурой.

**Anti-profile:**

- нет входящих заявок;
- нет повторяющихся диалогов;
- нет бизнес-боли;
- бюджет ниже минимально разумного уровня;
- запрос “просто поиграться с AI” без бизнес-задачи;
- технари, ищущие open-source DIY вместо внедрения под ключ.

### 1.4 Главные конверсионные механизмы

В v1.1 основной wow-механизм был roleplay demo: лид тестирует AI-продавца и сам спрашивает “как сделать такого же?”. В v1.2 roleplay остается важным, но становится одним из механизмов, а не единственным флоу.

Новые ключевые механизмы:

1. Simple Explanation — простое объяснение ценности AI-агента.
2. Microbusiness Assistant Pitch — AI как ассистент владельца.
3. Roleplay Demo — тест-драйв “такого же AI для вашего бизнеса”.
4. Light ROI Audit — быстрый расчет зоны потерь диапазоном.
5. Full ROI Audit — полноценный расчет окупаемости по метрикам.
6. Integration Architecture Map — демонстрация системного подхода к CRM/складу/таблицам/календарю/API.
7. Checkout / Call Close — перевод в спецификацию, контакт, созвон.
8. Low-fit Nurture — мягкое объяснение, когда решение станет актуально.

---

## 2. Ключевой архитектурный сдвиг v1.2

### 2.1 Было в v1.1

Упрощенно текущая логика:

```text
message
→ load state/history
→ extract client_facts
→ build dialog_state
→ roleplay detection/context gate
→ deterministic early exits
→ sales stage inference
→ route assembly
→ RAG/checkout if needed
→ LLM generation
→ filters
→ persist/log
```

Эта логика хороша как route-driven архитектура, но недостаточна для Adaptive Sales Intelligence.

### 2.2 Нужно в v1.2

Новая логика:

```text
message
→ load session context
→ protect roleplay isolation
→ update real B2B business profile
→ score client fit, pain, data readiness, friction, buying intent
→ choose conversation mode
→ choose wow mechanism
→ choose next best action
→ maybe calculate ROI in Python
→ compose prompt from strategy_result and roi_result
→ generate one natural answer
→ persist state/logs
```

### 2.3 Главное правило

ROI не является Route.

Route — технический путь обработки сообщения: GENERAL, RAG_REQUIRED, CHECKOUT, ROLEPLAY, EXIT_ROLEPLAY.

ROI — бизнес-стратегия и расчетный контекст, который может быть использован внутри GENERAL/CHECKOUT/RAG ответа. Поэтому ROI должен жить в Sales Intelligence Layer, а не в routing enum.

### 2.4 Новый доменный слой

В проект добавляется отдельный слой:

```text
Sales Intelligence Layer
```

Он отвечает за:

- business_profile;
- structured extraction;
- profile merge;
- conversation behavior signals;
- scoring;
- conversation mode;
- question budget;
- next best action;
- wow mechanism;
- ROI readiness;
- ROI calculation;
- bot guidance for prompt composer.

Основной LLM-продавец не должен сам решать стратегию с нуля. Он должен получать `strategy_result` и следовать ему.

---

## 3. Conversation Modes

Система поддерживает 6 режимов общения.

### 3.1 `simple_explainer`

Для кого:

- клиент только разбирается, что такое AI-агенты;
- не описал бизнес;
- задает общие вопросы;
- нет признаков зрелого бизнеса или явной боли.

Стиль:

- простой, человеческий;
- без слов “маржа”, “конверсия”, “воронка”, если клиент сам их не использует;
- максимум один легкий вопрос.

Цель:

- объяснить ценность;
- найти первый контекст бизнеса;
- не пугать глубокой квалификацией.

### 3.2 `microbusiness_helper`

Для кого:

- владелец сам отвечает клиентам;
- 0–1 менеджер;
- нет CRM или все в мессенджерах/таблицах;
- мало или средне заявок;
- боль: “не успеваю”, “забываю”, “все пишут мне”, “хаос в чатах”.

Стиль:

- поддерживающий;
- без корпоративной анкеты;
- главный угол: снять рутину, отвечать быстрее, не терять диалоги.

Что не спрашивать сразу:

- маржинальность;
- точную конверсию;
- стоимость лида;
- сложный ROI.

### 3.3 `light_roi_diagnostic`

Для кого:

- есть регулярные заявки;
- есть средний чек или его можно мягко узнать;
- есть боль в скорости ответа, хаосе, follow-up или потерях;
- клиент готов ответить на 3–5 простых вопросов, но не на полный аудит.

Цель:

- дать быстрый расчет диапазоном;
- показать порядок возможных потерь;
- аккуратно предложить углубиться или перейти к созвону.

### 3.4 `full_roi_audit`

Для кого:

- высокий поток лидов;
- высокий чек;
- есть менеджеры;
- есть CRM/таблицы;
- есть платный трафик;
- клиент дает цифры;
- friction низкий;
- клиент похож на ЛПР или сильного инициатора.

Цель:

- собрать метрики;
- посчитать ROI в Python;
- показать conservative/realistic/aggressive сценарии;
- закрыть на спецификацию/созвон.

### 3.5 `integration_discovery`

Для кого:

- клиент говорит про CRM, склад, наличие, таблицы, календарь, оплату, API, телефонию, несколько отделов;
- важна не только переписка, но и связь AI с внутренними процессами.

Цель:

- показать архитектурную зрелость Dami Works;
- собрать процессную схему;
- вести к технической спецификации.

ROI может быть вторичным. Главный wow — “они понимают, как это встроить в бизнес”.

### 3.6 `low_fit_nurture`

Для кого:

- нет заявок;
- нет повторяющихся диалогов;
- нет понятной бизнес-боли;
- бюджет ниже минимума;
- клиент пока просто интересуется.

Цель:

- не выдумывать ROI;
- не давить;
- объяснить, когда AI-агент станет актуален;
- возможно предложить простой стартовый сценарий.

---

## 4. Wow Mechanism Router

`wow_router` выбирает механизм, который в текущем turn создаст наибольший эффект без ощущения допроса.

### 4.1 Supported wow mechanisms

```text
simple_explanation
roleplay_demo
microbusiness_assistant_pitch
light_roi_audit
full_roi_audit
integration_architecture_map
checkout_or_call
nurture
```

### 4.2 Выбор механизма

Примеры:

```text
business_profile почти пустой
→ simple_explanation

owner_involved=true, operators_count<=1, pain=not_enough_time
→ microbusiness_assistant_pitch или roleplay_demo

lead_volume known, average_check known, pain known, data_readiness medium
→ light_roi_audit

lead_volume high, CRM/team/paid traffic/high check, friction low
→ full_roi_audit

integration_needs non-empty
→ integration_architecture_map

client asks price and buying_readiness high
→ checkout_or_call

low ICP fit
→ nurture
```

### 4.3 Не все клиенты должны видеть ROI

ROI показывается только если:

- он уместен для conversation_mode;
- есть хотя бы минимальные данные;
- расчет не будет ложной точностью;
- клиент не раздражен вопросами;
- ROI поможет продвинуть диалог, а не перегрузит его.

---

## 5. Целевая архитектура системы

### 5.1 Service topology

```text
Client channels: Telegram / Instagram / WhatsApp / Web
        ↓
Thin adapters
        ↓
POST /api/v1/chat
        ↓
FastAPI endpoint
        ↓
Conversation Orchestrator
        ↓
Session Context Manager
        ↓
Mode Guard / Roleplay Isolation
        ↓
B2B Sales Intelligence Layer
        ↓
Route Engine / RAG / Commercial Context
        ↓
Prompt Composer
        ↓
Gemini generation
        ↓
Output filters
        ↓
Persist session + logs
```

### 5.2 Architectural principles

1. `api.py` должен быть тонким endpoint layer.
2. Pipeline-level логика должна жить в `core/conversation_orchestrator.py`.
3. Sales logic не должна разрастаться внутри `gemini_service.py`.
4. ROI считается только в Python.
5. LLM извлекает и формулирует, но не считает бизнес-математику.
6. Roleplay state изолирован от B2B business_profile.
7. Route не должен подменять conversation strategy.
8. Основной бот получает готовый `strategy_result` и `roi_result`.
9. Один ответ — максимум один главный вопрос.
10. Question budget контролирует, когда бот задает вопрос, а когда обязан дать ценность.

---

## 6. Целевая структура проекта

Целевая структура:

```text
damiworks-ai-service/
  app/
    api.py
    main.py
    schemas.py
    settings.py

    core/
      conversation_orchestrator.py
      session_context.py
      tenant_context.py
      mode_guard.py
      logging_context.py

    routing/
      route_engine.py
      route_schemas.py
      route_heuristics.py

    sales_intelligence/
      schemas.py
      extractor.py
      profile_merger.py
      signal_analyzer.py
      scoring.py
      strategy_engine.py
      question_budget.py
      wow_router.py
      roi_readiness.py
      roi_engine.py
      defaults.py

    prompts/
      b2b_sales_prompt.py
      roleplay_prompt.py
      extraction_prompt.py
      prompt_composer.py

    roleplay/
      roleplay_detector.py
      roleplay_context_gate.py
      roleplay_state.py
      roleplay_generation.py

    services/
      gemini_service.py
      supabase_service.py
      rag_service.py
      checkout_service.py

    filters/
      output_filters.py
      commercial_filters.py
      roleplay_filters.py

    tests/
      test_extractor.py
      test_profile_merger.py
      test_strategy_engine.py
      test_roi_engine.py
      test_wow_router.py
      test_orchestrator_e2e.py
```

### 6.1 Module responsibilities

`core/conversation_orchestrator.py`:

- управляет request pipeline;
- вызывает session loading, intelligence, routing, generation, filters, persistence;
- не содержит бизнес-формул и prompt-тексты.

`core/session_context.py`:

- единый объект контекста на turn;
- хранит request, tenant, metadata, history, dialog_state, roleplay_state, business_profile, strategy_result, roi_result, routes, logs.

`sales_intelligence/*`:

- вся предметная логика квалификации, ROI и стратегии общения.

`prompts/prompt_composer.py`:

- собирает системные инструкции для LLM;
- инжектирует strategy_result, roi_result, route context;
- запрещает показывать внутренние JSON/score клиенту.

`roleplay/*`:

- изоляция roleplay;
- activation/context gate/exit;
- generation в B2C simulation mode.

`routing/*`:

- технические маршруты;
- не хранит ROI/qualification business logic.

---

## 7. Request Pipeline v1.2

Полный целевой pipeline для `POST /api/v1/chat`:

```text
1. Receive ChatRequest
2. Rate-limit check
3. Typing indicator fire-and-forget
4. Load tenant settings
5. Load session metadata
6. Fetch and merge recent chat history
7. Build SessionContext
8. Session timeout handling
   - roleplay context timeout: 6h
   - B2B qualification/dialog state timeout: 48–72h
9. Mode Guard
   - detect roleplay active
   - detect roleplay exit/commercial intent
   - prevent B2B extraction from roleplay messages
10. Roleplay detection and context gate
   - may early return if waiting for context
11. B2B Intelligence Update if allowed
   - Structured Extractor
   - Profile Merger
   - Signal Analyzer
   - Scoring
   - Strategy Engine
   - Wow Router
   - ROI readiness
   - ROI Engine maybe_calculate
12. Deterministic gates with strategy awareness
   - /start
   - portfolio/cases
   - price request through Commercial Policy, not blind hardcoded answer
13. Route assembly
   - GENERAL / RAG_REQUIRED / CHECKOUT / ROLEPLAY / EXIT_ROLEPLAY
14. RAG vector search if needed
15. Commercial context load if needed
16. Prompt Composer
   - compose B2B or roleplay prompt
   - inject strategy_result and roi_result safely
17. LLM generation
   - one pass preferred
18. Output filters
   - disabled for roleplay output
19. Format for messenger
20. Persist session metadata
21. Log chat with intelligence metadata
22. Async memory refresh if needed
```

### 7.1 Critical roleplay isolation rule

If `roleplay_demo_active=true` and user message is not a roleplay exit or commercial intent, do not update real `business_profile` from that message.

Reason: inside roleplay the user may pretend to be a customer of a fictional or demo business. These statements are not facts about the actual lead.

---

## 8. Session Metadata v1.2

`chat_sessions.metadata` must remain JSONB-friendly and backward-compatible.

### 8.1 Top-level schema

```json
{
  "dialog_state": {},
  "business_profile": {},
  "qualification_state": {},
  "roi_state": {},
  "conversation_behavior": {},
  "roleplay_state": {},
  "client_facts": {},
  "migration": {}
}
```

`client_facts` may remain for backward compatibility, but new code should prefer `business_profile`.

### 8.2 Field value wrapper

For extracted business data use this structure:

```json
{
  "value": null,
  "confidence": 0.0,
  "source_text": null,
  "extraction_type": "unknown",
  "last_updated_at": null,
  "conflict": false,
  "conflict_notes": []
}
```

Allowed `extraction_type`:

```text
explicit | inferred | default | unknown
```

### 8.3 `dialog_state`

Only milestone/funnel flags:

```json
{
  "pain_expressed": false,
  "demo_activated": false,
  "price_exposed": false,
  "close_consented": false,
  "contact_phone_collected": false,
  "automation_goal": null,
  "service_focus": null,
  "selected_product_id": null
}
```

### 8.4 `business_profile`

```json
{
  "business_niche": null,
  "offer_type": null,
  "geography_or_timezone": null,
  "lead_channels": [],
  "lead_volume_count": null,
  "lead_volume_period": null,
  "average_check": null,
  "currency": null,
  "conversion_rate": null,
  "gross_margin": null,
  "operators_count": null,
  "owner_involved": null,
  "crm_or_tracking_tool": null,
  "response_time": null,
  "working_hours_coverage": null,
  "after_hours_leads": null,
  "main_pains": [],
  "missed_leads_estimate": null,
  "lost_reasons": [],
  "integration_needs": [],
  "repetitive_questions_share": null,
  "qualification_needed": null,
  "capacity_constraint": null,
  "data_sources_available": [],
  "decision_maker_role": null,
  "urgency": null,
  "budget_sensitivity": null
}
```

Each scalar field should be stored as a wrapped extracted value where feasible. Lists may store items with confidence/source metadata if practical.

### 8.5 `qualification_state`

```json
{
  "conversation_mode": "simple_explainer",
  "wow_mechanism": "simple_explanation",
  "scores": {
    "icp_fit_score": 0,
    "roi_potential_score": 0,
    "operational_pain_score": 0,
    "data_readiness_score": 0,
    "conversation_friction_score": 0,
    "buying_readiness_score": 0,
    "ai_fit_score": 0,
    "integration_complexity_score": 0
  },
  "question_budget": {
    "max_questions_before_value": 1,
    "questions_asked_since_last_value": 0,
    "remaining_questions_before_value": 1
  },
  "last_value_given_at": null,
  "last_question_target_field": null,
  "last_next_best_action": null,
  "logging_reasons": []
}
```

### 8.6 `roi_state`

```json
{
  "roi_depth": "none",
  "last_roi_result": null,
  "last_shown_to_user_at": null,
  "assumptions": [],
  "missing_fields": [],
  "calculation_confidence": "low"
}
```

Allowed `roi_depth`:

```text
none | rough_estimate | light_roi | full_roi
```

### 8.7 `conversation_behavior`

```json
{
  "friction_signals": [],
  "engagement_level": "unknown",
  "user_answer_style": "unknown",
  "asked_price": false,
  "asked_how_it_works": false,
  "asked_for_demo": false,
  "explicit_commercial_intent": false,
  "irritated_by_questions": false
}
```

### 8.8 `roleplay_state`

Roleplay state should be isolated here, even if compatibility with old `dialog_state` keys is temporarily maintained:

```json
{
  "roleplay_demo_active": false,
  "roleplay_demo_topic": null,
  "roleplay_demo_awaiting_context": false,
  "roleplay_demo_context_summary": null,
  "roleplay_demo_context_source": null,
  "roleplay_demo_context_wait_count": 0,
  "roleplay_demo_no_file_fallback": false,
  "roleplay_started_at": null,
  "roleplay_last_active_at": null
}
```

---

## 9. Sales Intelligence Layer

### 9.1 Components

```text
Structured Extractor
→ Profile Merger
→ Signal Analyzer
→ Scoring
→ Strategy Engine
→ Question Budget
→ Wow Router
→ ROI Readiness
→ ROI Engine
```

### 9.2 Output: `strategy_result`

```json
{
  "conversation_mode": "microbusiness_helper",
  "wow_mechanism": "microbusiness_assistant_pitch",
  "roi_depth": "none",
  "scores": {
    "icp_fit_score": 68,
    "roi_potential_score": 32,
    "operational_pain_score": 82,
    "data_readiness_score": 25,
    "conversation_friction_score": 15,
    "buying_readiness_score": 40,
    "ai_fit_score": 74,
    "integration_complexity_score": 10
  },
  "question_budget": {
    "max_questions_before_value": 2,
    "questions_asked_since_last_value": 1,
    "remaining_questions_before_value": 1
  },
  "next_best_action": {
    "type": "give_value_then_ask_one_question",
    "value_message": "Клиент сам отвечает и не успевает. Уместнее продавать AI как ассистента владельца, а не как сложный ROI-калькулятор.",
    "question": "А клиенты чаще пишут вам в WhatsApp/Instagram или еще откуда-то?",
    "target_field": "lead_channels",
    "should_ask_now": true
  },
  "bot_guidance": {
    "tone": "simple_supportive",
    "avoid_topics": ["маржа", "конверсия", "сложный ROI"],
    "recommended_angle": "снять рутину с владельца и не терять диалоги",
    "should_offer_roi_audit": false,
    "should_offer_roleplay": true,
    "should_offer_call": false,
    "should_simplify": false,
    "should_stop_questioning": false
  },
  "logging_reasons": []
}
```

---

## 10. Structured Extraction

### 10.1 Model requirement

Use `gemini-3.1-flash-lite` with Structured Outputs / strict JSON schema.

LLM extraction is allowed to:

- extract business facts;
- classify intent/friction;
- infer soft signals with confidence;
- produce source_text for audit.

LLM extraction is not allowed to:

- calculate ROI;
- fabricate unknown values;
- overwrite high-confidence explicit facts with weak inference.

### 10.2 Fields to extract

Extractor should cover:

```text
business_niche
offer_type
lead_channels
lead_volume_count
lead_volume_period
average_check
currency
conversion_rate
gross_margin
operators_count
owner_involved
crm_or_tracking_tool
response_time
working_hours_coverage
after_hours_leads
main_pains
missed_leads_estimate
lost_reasons
integration_needs
repetitive_questions_share
qualification_needed
capacity_constraint
data_sources_available
urgency
decision_maker_role
budget_sensitivity
price_request
demo_interest
conversation_friction_signals
explicit_commercial_intent
```

### 10.3 Merge rules

1. Explicit high-confidence value may replace older value.
2. Inferred value must not overwrite explicit value unless confidence is clearly higher and conflict is logged.
3. Null/unknown never overwrites existing value.
4. Contradictions set `conflict=true` and append conflict notes.
5. Defaults are allowed only inside ROI assumptions, not as real extracted facts.
6. Roleplay messages must not update B2B business_profile unless message is a roleplay exit/commercial intent.

---

## 11. Conversation Strategy Engine

### 11.1 Scores

The system computes these scores on 0–100 scale:

```text
icp_fit_score
roi_potential_score
operational_pain_score
data_readiness_score
conversation_friction_score
buying_readiness_score
ai_fit_score
integration_complexity_score
```

### 11.2 Score semantics

`icp_fit_score` increases when:

- real business exists;
- lead flow exists;
- repeated conversations exist;
- digital channels exist;
- AI can handle repetitive or qualification tasks.

`roi_potential_score` increases when:

- lead volume is medium/high;
- average check is meaningful;
- paid traffic exists;
- lost leads are likely;
- conversion/margin data exists.

`operational_pain_score` increases when:

- owner is overloaded;
- response is slow;
- no 24/7 coverage;
- managers forget follow-ups;
- CRM is absent or chaotic;
- missed leads are frequent.

`data_readiness_score` increases when:

- lead volume known;
- average check known;
- conversion known;
- margin known;
- CRM/table/history exists.

`conversation_friction_score` increases when:

- client gives short/irritated answers;
- client asks “why so many questions?”;
- client refuses metrics;
- client only asks price and avoids context.

`buying_readiness_score` increases when:

- asks price;
- asks implementation timeline;
- wants demo;
- gives contact;
- describes urgent pain;
- is owner/decision maker.

`ai_fit_score` increases when:

- many repetitive questions;
- qualification needed;
- handoff to human needed;
- CRM/stock/calendar/payment integration useful;
- high chat volume.

`integration_complexity_score` increases when:

- CRM, warehouse, tables, calendar, payment, telephony, API or multi-step workflows are mentioned.

### 11.3 Question budget

```text
simple_explainer: max 1 question before value
microbusiness_helper: max 2 questions before value
light_roi_diagnostic: max 3 questions before insight/rough calculation
full_roi_audit: max 5 questions before intermediate insight
integration_discovery: max 3 questions before architecture insight
low_fit_nurture: max 0–1 question
```

If budget is exhausted, bot should give value before asking another question.

### 11.4 Next best action types

```text
answer_only
give_value_then_ask_one_question
ask_simple_context_question
ask_metric_for_roi
offer_roleplay_demo
offer_light_roi_audit
offer_full_roi_audit
offer_integration_discovery
offer_call_or_specification
simplify_and_stop_questioning
nurture
```

### 11.5 Mandatory UX rules

1. Answer the user’s question first.
2. Ask at most one main question in one response.
3. If friction is high, reduce depth and simplify.
4. If user asks price, do not dodge with a long questionnaire.
5. Microbusiness should not be asked about margin/conversion unless they consent to a quick estimate.
6. Mature SMB should not receive overly primitive “bot answers messages” explanation.
7. ROI with weak data must be shown only as a range and preliminary estimate.
8. No fake certainty.

---

## 12. ROI Engine

### 12.1 Hard rule

All ROI math happens in Python. Never via LLM.

LLM may only:

- extract fields;
- explain already-computed numbers;
- phrase assumptions safely.

### 12.2 ROI levels

```text
none
rough_estimate
light_roi
full_roi
```

### 12.3 `none`

Use when:

- business context unknown;
- no lead volume/check/pain;
- low-fit;
- conversation friction high;
- ROI would be fake.

Return qualitative insight only.

### 12.4 `rough_estimate`

Minimum data:

- lead volume;
- average check or approximate check;
- main pain/lost reason.

Output:

- rough lost revenue range;
- low confidence;
- clear assumptions.

### 12.5 `light_roi`

Minimum data:

- lead volume;
- average check;
- approximate conversion or conservative default;
- pain/lost reason;
- approximate leakage.

Output:

- lost revenue;
- optional margin estimate if margin exists;
- conservative/realistic ranges.

### 12.6 `full_roi`

Preferred data:

- leads per month;
- average check;
- conversion rate;
- gross margin;
- leakage rate;
- recoverability rate;
- AI monthly cost/setup cost config;
- optional time savings value.

Output:

- lost revenue;
- lost margin profit;
- recoverable revenue;
- recoverable margin profit;
- time savings value;
- monthly net effect;
- payback period;
- ROI percentage.

### 12.7 Formulas

```text
lost_revenue = leads_per_month * leakage_rate * conversion_rate * average_check

lost_margin_profit = leads_per_month * leakage_rate * conversion_rate * average_check * gross_margin

recoverable_margin_profit = lost_margin_profit * recoverability_rate

monthly_net_effect = recoverable_margin_profit + time_savings_value - monthly_ai_cost

payback_period_months = setup_cost / monthly_net_effect

roi_percentage = monthly_net_effect / monthly_ai_cost * 100
```

### 12.8 Scenarios

Every non-none calculation should support:

```text
conservative
realistic
aggressive
```

### 12.9 Safe phrasing rules

Allowed:

- “грубая прикидка”;
- “порядок цифр”;
- “если предположить”;
- “зона потерь может быть”;
- “точнее можно подтвердить по CRM/перепискам”.

Forbidden unless high-confidence data:

- “вы точно теряете X”;
- “вы гарантированно окупитесь за Y”;
- “мы вернем все потерянные лиды”.

### 12.10 `roi_result`

```json
{
  "roi_depth": "light_roi",
  "can_show_to_user": true,
  "calculation_confidence": "medium",
  "confidence_reasons": [],
  "scenarios": {
    "conservative": {},
    "realistic": {},
    "aggressive": {}
  },
  "assumptions": [],
  "missing_fields": [],
  "warnings": [],
  "user_safe_summary": "",
  "next_field_for_better_accuracy": null
}
```

---

## 13. Roleplay Demo Module

Roleplay remains a critical wow mechanism.

### 13.1 Roleplay activation

Triggers include:

- `/roleplay`;
- “отыграй роль продавца”;
- “будь менеджером моего бизнеса”;
- “давай я буду клиентом”;
- explicit demo interest from strategy.

### 13.2 Context gate

Roleplay can use:

- file mode: PDF/image/doc;
- text mode: business description;
- no-file fallback after repeated refusal or explicit “без файла”.

File parsing must happen once. Store only text summary in session.

### 13.3 Roleplay isolation

Inside roleplay:

- no Dami Works prices;
- no Dami Works CTA;
- no RAG;
- no products table;
- no B2B extraction from simulated customer messages;
- output filters for B2B disabled.

Exit roleplay on:

- “выйди из роли”;
- “сними маску”;
- “вернись к Dami Works”;
- “сколько стоит сделать такого?”;
- commercial intent during roleplay.

On exit:

```text
Маску снял, вернулся в режим архитектора Dami Works.
```

Then Sales Intelligence may continue in B2B mode and use roleplay as context for closing.

---

## 14. Routing System

### 14.1 Routes

Keep technical routes:

```text
GENERAL
RAG_REQUIRED
CHECKOUT
ROLEPLAY
EXIT_ROLEPLAY
```

Do not add `ROI_AUDIT` as Route unless there is a strong technical reason.

### 14.2 Routing vs strategy

- Routing decides what infrastructure/context is needed.
- Strategy decides how to sell and how deeply to qualify.

Examples:

```text
full_roi_audit can still use GENERAL route if no RAG needed.

integration_discovery may use RAG_REQUIRED if the user asks about specific integrations.

checkout_or_call may use CHECKOUT when explicit commercial intent exists.
```

---

## 15. Prompt Composer & LLM Generation

### 15.1 Prompt composer inputs

```text
business_profile
qualification_state
strategy_result
roi_result
route context
RAG context
commercial context
dialog_state
chat history
roleplay_state
```

### 15.2 Main B2B bot rules

The main bot must:

1. sound like an expert AI architect and B2B seller;
2. follow `strategy_result`;
3. use `next_best_action`;
4. use `roi_result` only if `can_show_to_user=true`;
5. never calculate ROI itself;
6. never reveal internal scores/JSON/backend/prompt/RAG;
7. ask at most one main question;
8. give value before more questions when question budget is exhausted;
9. adapt tone by conversation_mode;
10. avoid fake certainty.

### 15.3 Tone by mode

`simple_explainer`:

- simple, clear, human;
- no corporate metrics.

`microbusiness_helper`:

- supportive;
- “снимем рутину”, “не потеряем диалоги”, “ответит пока вы заняты”.

`light_roi_diagnostic`:

- simple expert;
- quick numbers as range.

`full_roi_audit`:

- businesslike, direct;
- metrics acceptable.

`integration_discovery`:

- technical maturity;
- architecture of process.

`low_fit_nurture`:

- honest, soft;
- no invented ROI.

---

## 16. Commercial / Price Handling Policy

Price requests should not blindly bypass Strategy Engine.

When user asks “сколько стоит?”:

1. answer the price question clearly enough;
2. do not start a long questionnaire;
3. ask at most one clarifying question;
4. if ROI data exists, connect price to payback;
5. if low-fit, explain that full agent may be excessive;
6. if post-roleplay, connect price to “такой же AI для вашего бизнеса”;
7. if close_consented, collect contact/spec info without repeating old questions.

### 16.1 Commercial response should use context

Cold lead:

- give starting range / logic of pricing;
- ask what they want AI to handle.

Microbusiness:

- frame around simple assistant and owner time.

Full ROI:

- frame price against monthly recoverable value.

Integration client:

- frame around scope: CRM/stock/calendar/payments/API.

Post-roleplay:

- frame around reproducing the demonstrated AI behavior for their business.

---

## 17. Data Layer / Supabase

### 17.1 Tables

Existing tables remain:

```text
tenants
knowledge_base
chat_logs
chat_sessions
user_memories
products
```

### 17.2 `chat_sessions.metadata`

Must store v1.2 metadata schema.

### 17.3 `chat_logs.metadata`

Each turn should log:

```text
conversation_mode
wow_mechanism
scores
roi_depth
calculation_confidence
next_best_action.type
question_budget
extraction_conflicts
assumptions
selected routes
roleplay isolation active yes/no
commercial policy branch if price request
```

Logs must not expose private prompts or secrets.

---

## 18. Cost / Efficiency Requirements

1. Use `gemini-3.1-flash-lite` for structured extraction, routing, light classification.
2. Use stronger model only where quality matters materially, especially roleplay demo if configured.
3. Keep one-pass final generation where possible.
4. Do not use LLM for Python-computable math.
5. Do not run extractor inside ordinary roleplay turns.
6. Avoid multiple LLM calls if deterministic strategy can decide.
7. Store parsed file summaries; never re-send media every turn.
8. Keep prompt context compact via prompt_composer.

---

## 19. Testing Requirements

### 19.1 Unit tests

Required:

- profile_merger explicit vs inferred update;
- conflict handling;
- strategy mode selection;
- score calculation;
- question budget exhaustion;
- wow mechanism selection;
- ROI readiness levels;
- ROI formulas;
- roleplay isolation;
- price handling policy.

### 19.2 E2E scenarios

Test at least:

1. Cold lead: “Что вы делаете?”
2. Microbusiness: “Я сам отвечаю в WhatsApp, не успеваю”
3. Light ROI: “У нас 20 заявок в день, чек 30к, менеджер иногда долго отвечает”
4. Full ROI: “100 лидов в день, amoCRM, 5 менеджеров, платный трафик”
5. Integration: “Нужно связать WhatsApp, CRM, склад и оплату”
6. Low fit: “У меня пока нет заявок, просто хочу AI”
7. Irritated user: “Зачем столько вопросов?”
8. Price-first user: “Сколько стоит?”
9. Roleplay activation
10. Roleplay active message does not update B2B profile
11. Roleplay exit: “Сколько стоит сделать такого?”
12. Contact collection after close
13. Returning user after 24h

---

## 20. Migration Plan

### Phase 0 — Documentation alignment

Replace old `project_specs.md` with this v1.2 target spec or add it as `project_specs_v1.2.md` and instruct Opus that v1.2 supersedes v1.1.

### Phase 1 — Structural skeleton

- create `core/conversation_orchestrator.py`;
- create `core/session_context.py`;
- keep behavior unchanged;
- move orchestration gradually out of `api.py`.

### Phase 2 — Metadata compatibility

- add v1.2 metadata schema;
- keep old `client_facts` compatibility;
- map old fields into new `business_profile` where safe.

### Phase 3 — Structured Extractor

- implement extractor using flash-lite structured output;
- implement profile_merger;
- disable extraction during roleplay turns.

### Phase 4 — Strategy Engine

- implement scores;
- implement conversation modes;
- implement question budget;
- implement wow_router.

### Phase 5 — ROI Engine

- implement roi_readiness;
- implement Python formulas;
- implement assumptions and confidence.

### Phase 6 — Prompt Composer

- update B2B prompt to follow strategy_result;
- ensure one question max;
- ensure ROI safe phrasing.

### Phase 7 — Commercial Policy

- replace blind hardcoded price early-exit with strategy-aware commercial response policy.

### Phase 8 — E2E tests and docs

- update CLAUDE.md;
- update README if needed;
- log strategy and ROI metadata;
- validate all critical scenarios.

---

## 21. Implementation Rules for Opus

1. Before coding, read this document fully.
2. Do not implement everything in one giant patch.
3. First propose migration plan and file-level changes.
4. Preserve current working behavior where possible.
5. Do not put Sales Intelligence logic inside `gemini_service.py` if it belongs in `sales_intelligence`.
6. Do not add ROI as a route unless strictly necessary.
7. Do not calculate ROI with LLM.
8. Do not update real business_profile from roleplay messages.
9. Keep backward compatibility with existing `dialog_state` and `client_facts` during migration.
10. Add tests with every phase.
11. Update `CLAUDE.md` after architecture changes.
12. If current code structure differs from this target spec, adapt intelligently and explain the tradeoff.
13. Never sacrifice roleplay wow quality while adding ROI.
14. Never turn the bot into a questionnaire.
15. The core product behavior is: choose the right next best action for the right client.

---

## Appendix A — First prompt to give Opus after replacing specs

```text
TASK: Прочитай новый project_specs.md v1.2 полностью и предложи план миграции без кода.

Контекст:
Мы меняем Dami Works AI Agent с route-driven roleplay-first архитектуры на Adaptive Sales Intelligence систему.

Важно:
Сначала НЕ пиши код.

Нужно:
1. Подтверди, как ты понял новую целевую архитектуру.
2. Найди в текущей кодовой базе, какие части соответствуют v1.2, а какие надо менять.
3. Составь поэтапный план миграции.
4. Укажи файлы, которые придется создать/изменить.
5. Укажи риски и как их снизить.
6. Отдельно объясни, как не сломать roleplay demo и текущий checkout flow.
7. Отдельно объясни, как изолировать roleplay messages от business_profile extraction.
8. После этого остановись и дождись моего подтверждения перед кодом.
```

---

*Документ является целевой спецификацией. При расхождении с v1.1 legacy Claude должен считать этот файл более приоритетным, если пользователь явно не сказал обратное.*