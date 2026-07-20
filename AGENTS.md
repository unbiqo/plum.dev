# Dami Works — Agent Guide

This repository is a **monorepo** for Dami Works, an AI-automation agency product. It contains a channel-agnostic AI sales backend, a Next.js marketing site, and a thin Telegram bot adapter. The system sells and demonstrates AI employees that handle incoming leads, qualification, follow-ups, and hand-off to humans over messengers and the web.

Read this file first before touching any code. It covers the repository layout, tech stack, how to run and test each component, and the conventions that keep the three sub-projects consistent.

---

## Project overview

**What this project does:**
- Provides an AI sales consultant for Dami Works (B2B lead capture on the web site).
- Runs interactive vertical demos: English School (`damiworks_english_school_demo`) and Medical Center (`damiworks_medical_center_demo`).
- Offers a custom roleplay demo (`damiworks_custom_demo`) where a user uploads documents and role-plays with an AI trained on their own materials.
- Bridges Telegram messages into the same backend via a thin adapter bot.
- Uses an **Adaptive Sales Intelligence** layer (Phases 1–9) to choose conversation depth, wow mechanism, and next best action per client, rather than relying on a rigid questionnaire.

**Key architectural documents:**
- `project_specs.md` — master specification (v1.2), in Russian. Source of truth for product intent.
- `docs/adaptive_sales_intelligence_v2.md` — snapshot of the implemented `sales_intelligence` layer.
- `project_specs_v1.1_legacy.md` — older roleplay-first architecture description.
- `CLAUDE.md` — generic coding caution guidelines (not project-specific).

---

## Repository structure

```
plum-dev/
├── damiworks-ai-service/     # FastAPI backend — core AI service
├── damiworks-site/           # Next.js 15 + React 19 marketing site and web chat
├── damiworks_tg_bot/         # aiogram 3 Telegram adapter bot
├── docs/                     # Architecture and spec docs
├── seed_damiworks.py         # One-off Supabase tenant/knowledge seed
├── sync_damiworks_infrastructure.py  # One-off prompt/knowledge sync
├── project_specs.md          # Master spec (Russian)
├── CLAUDE.md                 # Coding guidelines
└── local_launch_cmd.txt      # Local dev command cheat sheet
```

### AI service (`damiworks-ai-service/`)

FastAPI backend. All routes are under `/api/v1`.

- `app/main.py` — ASGI entry point, creates `FastAPI` app and mounts services in `app.state`.
- `app/api.py` — HTTP router: chat, lead, contact, quality feedback, custom-demo document upload, admin quality conversation endpoints.
- `app/config.py` — `Settings` dataclass, model profiles/pools, env parsing.
- `app/schemas.py` — Pydantic request/response models.
- `app/gemini_service.py` — LLM client, prompt assembly, route classification, answer generation.
- `app/llm_providers.py` — provider abstraction (`provider:model` refs, Anthropic/OpenAI clients, cooldowns) used by `gemini_service.call_model` for cross-provider fallback.
- `app/gemini_quota.py` — multi-key API quota manager and fallback logic.
- `app/llm_usage.py` — per-request token/cost tracking.
- `app/response_stylist.py` — deterministic "human style" post-processing: splits the final answer into 1–3 messenger parts (never drops content — overflow tail merges into the last part) and reduces it to exactly one question; optional cheap LLM repair pass is injected by the caller.
- `app/booking_guardrail.py` — booking slot guardrail: the model may only speak slots supplied by the slot provider; invented dates/times are replaced with the safe "уточню и вернусь" answer.
- `app/quality_eval.py` — offline judge rubric (naturalness, pain_discovery, funnel_progression, rag_factual_accuracy, guardrail_compliance); driven nightly by `scripts/nightly_quality_eval.py` into the `eval_runs` table.
- `app/supabase_service.py` — Supabase client: RAG, chat logs, sessions, leads, feedback, tenant prompts.
- `app/lead_notifier.py` — best-effort Telegram lead notifications to the owner.
- `app/web_site_intake_policy.py` / `app/web_site_lead.py` — B2B website intake and lead-stage state machine.
- `app/english_school_*.py` — English School demo (planner + writer + guardrails).
- `app/medical_center_*.py` — Medical Center demo (intake + planner + writer + safety guardrails + scheduling).
- `app/custom_demo_documents.py` — in-memory per-chat document store for the custom roleplay demo.
- `app/sales_intelligence/` — Adaptive Sales Intelligence layer (shadow profiler, scoring, strategy, ROI, commercial policy, question budget, wow router, insight extractor, etc.).
- `app/demo_knowledge/` — static markdown knowledge bases for demos.
- `tests/` — pytest suite, including phase-by-phase sales-intelligence tests and eval harness.
- `scripts/` — utility scripts (deploy, RAG indexing, Telegram chat ID helper, prompt sync, `nightly_quality_eval.py` offline judge batch, `cost_report.py` SLO report).
- `sql/` — Supabase schema migrations and helper SQL.
- `Dockerfile` / `docker-compose.yml` / `Caddyfile` — VPS deployment artifacts.

### Next.js site (`damiworks-site/`)

App Router marketing site and admin console.

- `app/page.tsx` — English homepage.
- `app/ru/page.tsx` — Russian homepage.
- `app/ru/demo/page.tsx` — Russian demo workspace.
- `app/quality-console/page.tsx` / `app/admin/feedback/page.tsx` — quality review console.
- `app/api/chat/route.ts` — proxy to FastAI `/api/v1/chat`.
- `app/api/contact/route.ts` — proxy to `/api/v1/contact`.
- `app/api/lead/route.ts` — proxy to `/api/v1/lead`.
- `app/api/custom-demo/upload/route.ts` — proxy to `/api/v1/custom-demo/documents`.
- `app/api/message-feedback/` / `app/api/quality-feedback/` / `app/api/quality/conversations/` — quality/admin proxies.
- `components/` — page sections and chat widgets (`LiveChat`, `MedicalCenterChat`, `EnglishSchoolChat`, `CustomDemoChat`, `QualityConsoleClient`, etc.).
- `lib/` — shared logic: `i18n.ts` (copy dictionary), `intake.ts` (scoring/recommendation), `chatSession.ts` (localStorage sessions), `freeform.ts` (regex extraction), `qualityFeedback.ts`, etc.
- `tests/` — standalone assertion-based tests run with `tsx`.
- `middleware.ts` — locale detection and redirect (`en` / `ru`).

### Telegram bot (`damiworks_tg_bot/`)

Thin adapter. No business logic lives here.

- `bot.py` — message handlers, attachment download, proxy to AI service.
- `config.py` — Pydantic settings from `.env`.

---

## Technology stack

| Concern | Technologies |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic |
| LLM / embeddings | Google Gemini, Anthropic Claude, OpenAI (via `app/llm_providers.py`) |
| Database / RAG | Supabase (PostgreSQL + pgvector) |
| Frontend | Next.js 15, React 19, TypeScript 5, Tailwind CSS 3 |
| Telegram | aiogram 3 |
| Dev tooling | pytest, tsx, python-dotenv |
| Deployment | Docker, Docker Compose, Caddy, Vercel |

**Model profiles (AI service):**
- Default fast model: `gemini-3.1-flash-lite` (CHEAP tier; cross-provider fallback `openai:gpt-5.4-nano`)
- WRITER tier: `anthropic:claude-sonnet-5` → `google:gemini-3.5-flash`; escalation `anthropic:claude-opus-4-8`
- Escalation model: `gemini-3-flash-preview` (never first in a live pool — 503 history broke the 55s budget)
- JUDGE (offline quality_eval): `gemini-3.1-pro` via Batch API
- Embedding models: `text-embedding-004`, `gemini-embedding-001`

Each task profile (`router`, `sales_writer`, `rag_writer`, `medical_planner`, etc.) has its own ordered pool in `app/config.py:MODEL_PROFILES` and can be overridden via env vars like `ROUTER_MODEL_POOL`, `SALES_WRITER_MODEL_POOL`, etc. Pool entries are `provider:model` refs (`google:…`, `anthropic:…`, `openai:…`, or bare `gemini-…` = google) with per-entry timeout/retries, resolved by `app/llm_providers.py`; the shared per-answer budget is 55s.

---

## Build and run commands

### AI service (`damiworks-ai-service/`)

Create venv, install deps, copy env, run:

```bash
cd damiworks-ai-service
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Linux/Mac
cp .env.example .env
# edit .env with real GEMINI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Health check: `curl http://localhost:8010/health` → `{"status":"ok"}`.

### Telegram bot (`damiworks_tg_bot/`)

```bash
cd damiworks_tg_bot
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env  # or create .env with BOT_TOKEN, AI_SERVICE_URL, INSTANCE_ID
.venv/Scripts/python.exe bot.py
```

Required `.env`:
- `BOT_TOKEN`
- `AI_SERVICE_URL` (e.g. `http://127.0.0.1:8010/api/v1/chat`)
- `INSTANCE_ID` (default `damiworks_dev`)

### Next.js site (`damiworks-site/`)

```bash
cd damiworks-site
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # Linux/Mac
# edit .env.local: FASTAPI_URL, NEXT_PUBLIC_CALENDLY_URL, NEXT_PUBLIC_WHATSAPP_URL
npm install
npm run dev
```

Production must set `FASTAPI_URL` to the backend base URL (e.g. `https://api.damiworks.com`). In dev it falls back to `http://localhost:8010`.

### Full monorepo local dev

`local_launch_cmd.txt` is a Windows/PowerShell-oriented cheat sheet. In short, run the three services in separate terminals: AI service on port 8010, Telegram bot, and Next.js site.

---

## Testing instructions

### AI service tests

Run from `damiworks-ai-service/`:

```bash
pytest tests/ -q
```

Live tests that call the real Gemini API are gated by the `live` marker. To run them:

```bash
RUN_LIVE_EVALS=1 pytest tests/ -q -m live
```

Key test files:
- `tests/test_smoke.py` — rate limits, session TTL, output sanitizers, roleplay helpers.
- `tests/test_sales_intelligence_phase*.py` — phase tests for the adaptive intelligence layer.
- `tests/test_medical_center_demo.py` — medical demo safety and flow.
- `tests/test_english_school_demo.py` — English school demo.
- `tests/test_damiworks_lead_lifecycle.py`, `test_lead_capture.py`, `test_web_site_lead.py`, `test_web_site_channel.py`, `test_web_site_freeform.py` — website consultant behavior.
- `tests/test_price_hiding.py`, `test_calendly_cta.py`, `test_quality_feedback.py` — policy-specific tests.
- `tests/test_custom_demo_documents.py` — document upload/chunk/retrieval.
- `tests/eval_runner.py` — black-box eval harness that drives conversations through `/api/v1/chat` and writes `eval_reports/latest.md` and `latest.json`.

### Site tests

Run from `damiworks-site/`:

```bash
npm test
```

This expands to a chain of `npx tsx` invocations:

```bash
npx tsx tests/intake.test.ts
npx tsx tests/chatSession.test.ts
npx tsx tests/calendly.test.ts
npx tsx tests/freeform.test.ts
npx tsx tests/medicalDemo.test.ts
npx tsx tests/medicalSummary.test.ts
npx tsx tests/qualityFeedback.test.ts
```

Tests use Node's built-in `assert` module; no Jest or Vitest is installed.

### Telegram bot

The bot has no automated test suite. Manual verification: start the bot, send `/start`, `/reset`, text, and a document/photo, and confirm responses come from the AI service.

---

## Code organization and conventions

### Backend conventions

- **FastAPI + async.** Route handlers are async; blocking Supabase calls are wrapped with `asyncio.to_thread`.
- **Stateless sessions.** The server reconstructs session state from the full `chat_history` sent by the frontend (or an empty history from Telegram). Persistent metadata lives in `chat_sessions`.
- **Single request pipeline.** Every chat request goes through: tenant load → history load → extraction/legacy facts → route classification → RAG → LLM generation → output filters → persistence.
- **Deterministic guardrails.** Critical safety paths (emergency red flags, injection, address handling, price hiding) short-circuit before LLM calls. Vertical demos use an LLM planner + writer + deterministic guardrails.
- **Model pools.** Every LLM call passes a `model_profile` mapped to a fallback pool in `config.py`. Never call Gemini with a single hardcoded model.
- **Cost tracking.** Every LLM call is tracked via `llm_usage.py` context vars and stored in `llm_call_logs`.
- **Best-effort side effects.** Lead persistence, notifications, and logging are wrapped in `try/except` and never break the chat response.
- **No LLM math.** ROI and business calculations are done in Python only (`roi_engine.py`, `roi_readiness.py`); LLMs never compute numbers.
- **Russian-first UX.** Most user-facing text and intent patterns are in Russian/Kazakh context. Code comments are English.
- **Sales Intelligence kill switch.** `INTELLIGENCE_SHADOW_ENABLED` (default `true`) disables the whole adaptive layer when set to `false`, restoring legacy behavior.

### Frontend conventions

- **App Router.** No `pages/` directory. Routes live under `app/`.
- **Client components** use `'use client'` at the top; everything else defaults to a Server Component.
- **Tailwind utility-first.** Custom semantic colors in `tailwind.config.ts`: `bg`, `surface`, `border-col`, `primary`, `secondary`, `accent`, `accent-soft`.
- **Copy dictionary.** All UI copy is centralized in `lib/i18n.ts` for `en` and `ru` locales.
- **Local state only.** No Redux/Zustand. Persistence uses `localStorage` (chat IDs) and `sessionStorage` (messages).
- **Fetch through Next.js API routes.** Client code never calls FastAPI directly; it goes through `app/api/*` proxies.
- **Path alias.** `@/` maps to the project root via `tsconfig.json`.
- **Strict TypeScript.** `strict: true` is enabled.

### Telegram bot conventions

- **Thin adapter.** The bot only converts Telegram messages into `ChatRequest` payloads and forwards the AI service `answer` back. It has no conversation logic.
- **Attachments.** Documents and photos are downloaded via the Telegram file API, base64-encoded, and passed as `ChatAttachment` to the AI service. Max size: 6 MB.
- **Commands.** `/start` and `/reset` set `reset_context=True` to clear the server-side session.

---

## Environment variables

### AI service (required and important)

Required in `damiworks-ai-service/.env`:

```env
GEMINI_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

Optional operational variables:

```env
LEAD_TELEGRAM_BOT_TOKEN=        # owner lead notifications; empty disables
LEAD_TELEGRAM_CHAT_ID=
QUALITY_CONSOLE_ADMIN_TOKEN=    # required for admin quality endpoints
ANTHROPIC_API_KEY=              # enables anthropic:* pool entries (CLAUDE_API_KEY alias)
OPENAI_API_KEY=                 # enables openai:* pool entries
LEAD_COST_BUDGET_USD=0.15       # soft per-lead cost guard
INSIGHT_EXTRACTOR_ENABLED=true
MAX_HISTORY_MESSAGES=15
RAG_MATCH_COUNT=3
RAG_CHUNK_MAX_CHARS=1800
RAG_CONTEXT_MAX_CHARS=5500
SUMMARY_AFTER_MESSAGES=15
ENABLE_B2B_MEMORY_SUMMARY=true
INTELLIGENCE_SHADOW_ENABLED=true
ENABLE_GENERATION_FALLBACK=false
ROUTER_MODEL_POOL=              # comma-separated model names
SALES_WRITER_MODEL_POOL=
# ... see config.py:_PROFILE_ENV_VARS for all per-profile overrides
```

### Telegram bot

```env
BOT_TOKEN=...
AI_SERVICE_URL=...
INSTANCE_ID=damiworks_dev
```

### Next.js site

```env
FASTAPI_URL=...                 # backend base URL; fallback to localhost in dev
NEXT_PUBLIC_CALENDLY_URL=...    # enables Calendly CTA
NEXT_PUBLIC_WHATSAPP_URL=...    # enables WhatsApp CTA
```

`x-admin-token` header is passed to backend quality endpoints; it is stored in `sessionStorage` on the client.

---

## Deployment

### VPS (recommended for AI service)

The AI service is primarily deployed on a VPS via Docker:

```bash
cd damiworks-ai-service
cp .env.example .env  # fill required values
docker compose up -d --build
```

The included `Caddyfile` proxies `api.damiworks.com` → `localhost:8000` with automatic TLS. Set the DNS `A` record for `api.damiworks.com` to the VPS IP before enabling Caddy.

`Dockerfile` uses `python:3.11-slim`, runs as a non-root `appuser`, exposes `8000`, and includes a healthcheck.

### Vercel

- `.vercel/project.json` files show linked Vercel projects. By default, Vercel detects the Next.js frontend and (separately) the Python FastAPI service.
- The frontend proxies chat to the backend via `FASTAPI_URL`, which must be set in the Vercel environment.
- The backend's env variables (`GEMINI_API_KEY`, `SUPABASE_*`) must be set on the backend's Vercel deployment if it is deployed there.

### Supabase

Run the SQL migrations in `damiworks-ai-service/sql/` to create the required tables:

- `tenants`, `tenant_prompts`
- `knowledge_base` / `rag_documents` (vector store)
- `chat_logs`, `chat_sessions`, `ai_conversations`, `ai_conversation_messages`
- `ai_message_feedback`, `damiworks_leads`, `llm_call_logs`
- `omnichannel_memory`, `user_memories`, `products`

Use `seed_damiworks.py` and `sync_damiworks_infrastructure.py` to bootstrap the Dami Works tenant (`instance_id = damiworks_dev`) and knowledge-base embeddings. These are one-off scripts; do not run them repeatedly in production without understanding that they clear/replace existing tenant chunks.

---

## Security considerations

- **Secrets in `.env` files.** All three sub-projects load secrets from `.env` (AI service + Telegram bot) or `.env.local` (Next.js site). Never commit these files. `.gitignore` already excludes them.
- **Supabase service role key.** The backend uses the **service role** key for full database access. Keep it secret and rotate it if leaked.
- **Admin token.** Quality console and admin endpoints require `QUALITY_CONSOLE_ADMIN_TOKEN` passed as the `x-admin-token` header. Do not expose this value client-side.
- **Gemini API keys.** Stored in `GEMINI_API_KEY`. The quota manager supports a single key today; rotation is manual.
- **Telegram bot tokens.** `BOT_TOKEN` / `LEAD_TELEGRAM_BOT_TOKEN` grant full bot access.
- **Attachment size limits.** Telegram attachments are capped at 6 MB in the bot; the custom demo upload endpoint also enforces backend-side limits.
- **Output filters.** The backend applies always-on safety filters plus mode-aware sales filters. Do not bypass them without checking the medical and roleplay-specific guardrail consequences.
- **No hardcoded pricing in user prompts.** The architecture pushes commercial scripts and FAQ answers into the `tenants` table / RAG. Avoid adding hardcoded Russian business copy to route handlers unless the spec explicitly requires it.
- **Medical demo safety.** The medical center guardrails explicitly forbid diagnosis, invented prices/doctors, and contact collection from children. Any change to this module must preserve those guardrails.

---

## Common tasks

**Add a new conversation mode (Adaptive Sales Intelligence):**
1. Add the value to `ConversationMode` in `app/sales_intelligence/schemas.py`.
2. Update maps in `app/sales_intelligence/strategy_engine.py` (`_TONE_BY_MODE`, `_AVOID_BY_MODE`, `_ANGLE_BY_MODE`, `_TARGET_FIELD_BY_MODE`, `_DEFAULT_NBA_BY_MODE`).
3. Update `MODE_QUESTION_LIMITS` in `app/sales_intelligence/question_budget.py`.
4. Update `_MODE_WOW_FALLBACK` / allowed sets in `app/sales_intelligence/wow_router.py`.
5. Add a selection rule in `strategy_engine._select_mode`.
6. To enable prompt behavior, add the mode to `prompt_composer.ENABLED_MODES` and provide an instruction (tenant override key `prompt_mode_<mode>`).
7. Add commercial framing in `app/sales_intelligence/commercial_policy.py` if price-relevant.
8. Add tests in `tests/test_sales_intelligence_phaseN.py` and an E2E row.

**Run a full black-box eval:**

```bash
cd damiworks-ai-service
python tests/eval_runner.py
```

This writes `eval_reports/latest.md` and `eval_reports/latest.json`.

**Index RAG documents:**

```bash
cd damiworks-ai-service
python scripts/index_vector_knowledge_base.py
```

---

## Notes for AI agents

- This is a **monorepo** with three independent runtimes. Changes in one sub-project usually do not require changes in the others unless the `ChatRequest`/`ChatResponse` contract or instance IDs change.
- Before changing the request/response schema (`app/schemas.py`), check the Next.js proxy routes and the Telegram bot payload builder.
- Before touching `app/api.py`, read `docs/adaptive_sales_intelligence_v2.md` to understand where the new sales-intelligence layer hooks in and what is legacy vs. new behavior.
- Keep changes minimal. Match the existing style: English comments, Russian user-facing strings, deterministic guardrails around safety-critical paths, and best-effort side effects.
- Always verify with the relevant test suite before claiming a task is complete.
