from __future__ import annotations

import asyncio
import base64
import binascii
import difflib
import json
import logging
import re
from threading import Lock
from urllib import request as urllib_request
from urllib.parse import urlparse

from google import genai
from google.genai import errors, types
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

try:
    from google.api_core import exceptions as google_api_exceptions
except Exception:  # pragma: no cover - optional dependency path
    google_api_exceptions = None

from .config import Settings
from .gemini_quota import (
    GeminiQuotaExhausted,
    GeminiQuotaLease,
    GeminiQuotaManager,
    estimate_embedding_tokens,
    estimate_tokens,
    normalize_model_name,
)
from .schemas import ChatAttachment, ChatHistoryMessage, Route


logger = logging.getLogger(__name__)

ECONOMY_MAX_OUTPUT_TOKENS = 384
COMPLETION_RETRY_MAX_OUTPUT_TOKENS = 512
MAX_MULTIMODAL_ATTACHMENT_BYTES = 6 * 1024 * 1024
BASE_ASSISTANT_OFFER_NAME = "Базовый ИИ-ассистент"
AUTO_CART_OFFER_NAME = "Авто-корзина под ключ"
AI_AGENT_IMPLEMENTATION_OFFER_NAME = "ИИ-агент под ключ"

ROUTER_SYSTEM_PROMPT = """You are a strict multi-label router for an AI development and automation sales assistant.

Analyze the user's message and select ALL applicable categories from the list:
GENERAL - greetings, small talk, unrelated messages, or simple non-technical questions.
ROLEPLAY - the user asks to demonstrate, simulate, roleplay, act as a seller/manager/consultant in a niche, or show how the AI would sell a product/service in a pretend conversation.
RAG_REQUIRED - AI agents, knowledge bases, integrations, CRM, funnel automation, smart carts, implementation details, cases, portfolio, or any question requiring exact knowledge-base facts.
CHECKOUT - the user wants pricing, a project estimate, to buy a ready solution, book a call, start implementation, create a cart/deal, or proceed with purchase.
EXIT_ROLEPLAY - the conversation is currently in a roleplay/demo/simulation and the user wants to stop acting, remove the role mask, return to the real AI-agent/Plum Dev discussion, get back to business, or asks how much it costs to build a bot like the demonstrated roleplay.

Do not infer CHECKOUT from a generic confirmation alone. Contextual stage transitions are handled by the dedicated sales-stage router.
If EXIT_ROLEPLAY applies, include EXIT_ROLEPLAY together with RAG_REQUIRED when the user asks about AI agents, bot cost, automation, or implementing a similar bot.
If ROLEPLAY applies, return ROLEPLAY. Do not also return RAG_REQUIRED unless the user is asking about Plum Dev implementation facts.

Your response must be a valid JSON array of strings.
Examples:
["GENERAL"]
["ROLEPLAY"]
["RAG_REQUIRED"]
["RAG_REQUIRED", "CHECKOUT"]
["EXIT_ROLEPLAY", "RAG_REQUIRED"]

Do not explain. Do not wrap the JSON in markdown."""

EXIT_ROLEPLAY_ROUTER_RULE = """Additional route:
ROLEPLAY - use when the user asks to demonstrate, simulate, roleplay, or act as a seller/manager/consultant in a niche.
EXIT_ROLEPLAY - use when the recent conversation is a roleplay/demo/simulation and the user semantically asks to stop it or return to the real AI-agent/Plum Dev business discussion. This includes indirect wording such as "хватит", "завязывай", "давай к делу", "сними маску", "выйди из роли", "вернись к ИИ", "я про ИИ агента", or "сколько стоит сделать такого бота".
If EXIT_ROLEPLAY applies and the user asks about building, pricing, automation, or AI agents, return both EXIT_ROLEPLAY and RAG_REQUIRED."""

SALES_STAGE_ROUTER_PROMPT = """You classify the next sales-dialog stage for an AI development and automation consultant.

Analyze the semantic pair: the latest assistant question/offer plus the current user answer. Do not rely on fixed keywords or exact phrases.

Stages:
- none: no commercial stage transition.
- stage_2_comparison: the assistant offered to explain/select/show solution options, and the user semantically agrees to learn the options. This means consultation and comparison only. No product card, cart, checkout, or CREATE_CART.
- stage_3_price: the assistant already compared/explained service packages or asked whether to show exact project cost, and the user semantically agrees. This means present the commercial estimate only. No product card, cart, checkout, or CREATE_CART.
- stage_4_checkout: the assistant already presented concrete project terms and asked whether to proceed, start, book a call, or оформить заявку, and the user semantically agrees to proceed. Only this stage may create a cart/product card/deal handoff.

Return only valid JSON:
{"stage":"none|stage_2_comparison|stage_3_price|stage_4_checkout","commercial_intent":true|false,"checkout_intent":true|false}

Rules:
- If the latest assistant offer was only to show/explain/select options, an affirmative user answer is stage_2_comparison, not checkout.
- If the latest assistant message already gave prices and the user agrees to proceed, classify stage_4_checkout.
- checkout_intent can be true only for stage_4_checkout."""

CONTENT_FOLLOWUP_ROUTER_PROMPT = """You classify non-commercial content follow-up intent for an AI development and automation consultant.

Analyze the semantic pair: the latest assistant question/offer plus the current user answer. Do not rely on fixed keywords or exact phrases.

Return only valid JSON:
{"content_followup":"none|mechanism_detail|safety_quality_detail"}

Meanings:
- none: no non-commercial content follow-up.
- mechanism_detail: the assistant offered to explain how the AI solution works, its architecture, data flow, funnel logic, integrations, or knowledge-base behavior, and the user semantically agreed.
- safety_quality_detail: the assistant offered to explain reliability, security, implementation quality, data handling, support process, portfolio, or why the delivery approach is trustworthy, and the user semantically agreed.

Rules:
- Classify mechanism_detail or safety_quality_detail ONLY when the latest assistant message explicitly asked/offered to explain that topic in more detail and the user semantically agreed.
- If the latest assistant message merely answered a mechanism/safety/quality question and did not offer a follow-up, a short acknowledgement is none.
- Do not attach a user acknowledgement to an older assistant offer if the latest assistant turn was a substantive answer.
- If the assistant asked a combined question with both mechanism and quality/safety, choose the dominant useful next step from the wording. Prefer mechanism_detail if the user originally asked how it works; prefer safety_quality_detail if the user originally asked whether it is safe or about quality.
- This classifier is not for price, options, or checkout stages."""

GENERAL_SYSTEM_PROMPT = """You are a concise Russian-speaking assistant for the active tenant.
Answer simple general messages naturally and briefly.
Do not provide exact implementation, integration, pricing, portfolio, or delivery facts without knowledge-base context when those facts should come from tenant data.
If the current user message is only a short acknowledgement after an informational answer, acknowledge briefly. Do not introduce a new package recommendation, price, cart, call booking, or checkout unless the latest assistant message explicitly asked for that commercial next step.
If the user sends only a greeting, answer only with a greeting and a neutral offer to help.
For greetings, do not mention previous dialog topics, project facts, cases, integrations, or "continue the dialog" unless the user explicitly asks about them.
If the user asks about exact service facts, say that you need to check the knowledge base."""

HYDE_SYSTEM_PROMPT = """You improve retrieval queries for a tenant AI-development RAG system.

Convert the user's noisy message into a compact search text for the knowledge base.
Include:
- the likely service or offer names;
- AI agent, knowledge base, CRM, integration, funnel, smart cart, automation, case, demo, price, or checkout keywords when relevant;
- a short hypothetical answer fragment with the facts that would satisfy the question.

Do not answer the user directly. Do not invent specific facts that are not implied by the request.
Return plain text only, no markdown, no JSON."""

FINAL_SYSTEM_PROMPT = """You are an expert AI architect and sales consultant for the active tenant.

If RAG context is provided, answer questions about AI agents, automation, integrations, cases, delivery process, and service details strictly from it.
If the question is simple/general and RAG is not needed, answer briefly and naturally.
If the user sends only a greeting, answer only with a greeting and a neutral offer to help; do not mention previous dialog topics, project facts, cases, integrations, or "continue the dialog".
If the question needs exact service, portfolio, integration, or implementation facts and RAG context is missing or insufficient, clearly say that the knowledge base does not contain enough data.
If commercial context is provided, use it only for explicit commercial questions about prices, packages, purchase, payment, project estimate, call booking, cart, or checkout.
Never mention prices, package prices, discounts, payment, cart, call booking, or checkout unless the current user turn is semantically commercial in context, either by direct request or by confirming the latest assistant question about that commercial step.
Treat a semantically affirmative answer as commercial only through the latest assistant question it answers, and advance exactly one dialog stage.
For architecture, integration, data flow, knowledge-base, CRM, support, reliability, or implementation-detail questions, do not mention prices even if commercial context contains prices.
If the request is both consultative and commercial, answer the consultative part and briefly explain the purchase next step.
If long-term B2B memory context is provided, use it to continue negotiations from the right point without restating that you have memory.

Dialog stages:
- Stage 1 Qualification: learn the business niche, current sales process, channels, CRM/website stack, and the bottleneck when needed.
- Stage 2 Consultation and Comparison: when the user semantically agrees to learn/select options, compare relevant AI-service options, explain value, and do not mention or trigger a product card/cart/checkout.
- Stage 3 Price Presentation: only after the user agrees after comparison, present prices or estimate ranges from dynamic product context.
- Stage 4 Checkout: only after the user agrees with the presented project/package may checkout/card/cart/call handoff be handled by backend.
- An affirmative answer advances exactly one stage from the assistant's latest question. Agreement to see options is Stage 2, not Stage 4.

Follow-up discipline:
- Never ask combined or double next-step questions in one message. Do not ask variants like "shall I explain how it works and why quality matters?".
- Offer only one concrete next step at a time: architecture detail, reliability/process detail, project estimate, call booking, or checkout.
- If the user agrees to a previous informational follow-up, answer that exact follow-up with new detail instead of repeating the short prior explanation.

Sales style:
- Be concise by default: 1-3 short sentences.
- Follow the unified AI development commercial block: outcome-first sales, dynamic pricing, varied CTAs, refusal handling, practical scoping, and clean handoff to checkout or call.
- Use only prices provided in the dynamic product context. Do not invent prices.
- If project pricing is not covered by the dynamic product context, say: "Нужно быстро уточнить вводные, чтобы посчитать проект без выдуманных цифр." and do not name a number.
- One short sentence is enough when it fully answers the question.
- Keep each sentence short. Prefer two short sentences over one long sentence.
- Use simple everyday wording. Avoid technical terms unless the user asks for architecture detail.
- Explain technical concepts plainly: what connects to what, what is automated, what the business gets, and what changes in the funnel.
- Do not add extra architecture or implementation details to practical questions.
- Do not write catalog-style phrases unless the user explicitly asks for the full catalog.
- For availability or price questions, use simple wording and mention only the relevant service/package.
- Do not explain the full checkout/call handoff flow unless the user asks how to start or says they are ready.
- Do not close every answer with a sales question. Many good answers should end without a question.
- Double-question ban: never ask combined next-step questions in one message. Offer exactly one concrete next step at a time: architecture detail, reliability/process detail, project estimate, call booking, or checkout.
- Never end two consecutive assistant messages with the same pattern, especially repeated "Хотите...".
- If the user refuses a side topic, do not push that topic again. If the user refuses purchase, handle the objection professionally instead of dropping the sale.
- For security, privacy, data access, reliability, or risk questions, answer the concern and do not add a purchase CTA.
- Use varied, context-aware next steps only when natural: brief clarification, option comparison, estimate, call handoff, or no CTA at all.
- If the user uses a platform, tool, CRM, or competitor name, answer only from tenant context or RAG.

Answer in Russian. Use plain text or Telegram-safe HTML. Do not use Markdown such as **bold**, star bullets, or [text](url) links.
Do not invent portfolio facts, implementation guarantees, discounts, timelines, integrations, or prices outside the provided context."""

MEMORY_SUMMARY_SYSTEM_PROMPT = """You write dry CRM memory notes for a B2B AI development sales assistant.

Read the dialog. Extract only what matters for a future B2B deal:
- what business niche and sales process the client has;
- which AI-agent, funnel automation, CRM integration, knowledge base, or smart-cart solution they discussed;
- what budget, timeline, stack, decision criteria, objections, or constraints they asked about;
- the next useful follow-up point.

Write 2-4 concise Russian sentences. Do not invent facts."""

COMMERCIAL_GUARD_PROMPT = """Commercial guardrail:
- Mention prices, package prices, discounts, payment, cart, checkout, call booking, or purchase steps only when the current user turn is semantically commercial in context, either by direct request or by confirming the latest assistant question about that commercial step.
- A semantically affirmative answer is commercial only through the latest assistant question it answers, and it advances exactly one dialog stage.
- Use only prices provided in the dynamic product context.
- If a requested project or package price is not fully covered by the dynamic product context, say: "Нужно быстро уточнить вводные, чтобы посчитать проект без выдуманных цифр." and do not invent numbers.
- For architecture, integration, knowledge-base, CRM, support, reliability, security, or process questions, do not mention prices even if commercial context contains prices.
- Scope, stack, timeline, integration, or feature questions are not price questions unless the user explicitly asks price or purchase."""


STYLE_GUARD_PROMPT = """Style guardrail:
- Answer briefly by default. One short sentence is often enough; use 2-3 only when useful.
- Keep sentences short. Split long thoughts into shorter sentences.
- Use simple customer-friendly language.
- Do not copy bureaucratic or overloaded technical wording from RAG/context. Translate it into everyday Russian focused on business outcomes: fewer missed leads, faster replies, cleaner CRM, higher conversion, and less manual work.
- When RAG contains dry security or reliability language, explain it calmly and humanly without promising that the system is perfect. Never write absolute guarantees such as "полностью безопасно", "без рисков", or "точно не сломается".
- Explain any concept in very simple everyday Russian by default. Add technical detail only when the user explicitly asks for architecture, integrations, stack, or proof.
- Speak like an experienced AI architect who can explain complex automation to a business owner.
- Avoid overloaded technical wording such as "оркестрация микросервисов", "эмбеддинги", "векторизация", "ретривер", "LLM пайплайн", "инференс", "токенизация", unless the user explicitly asks for technical depth.
- If a technical fact is necessary, explain it in business language instead of naming the term.
- Do not add extra architecture or stack details to practical questions.
- For "Что такое <solution>?" answer in 1-2 simple service sentences: what it automates and why the client should care.
- Any follow-up question to the client must be separated from the main answer by a blank line (`\n\n`).
- Ideal style pattern:
  Client: "Что такое ИИ-агент?"
  Bot: "Это сотрудник в чате, который отвечает клиентам, квалифицирует заявки и передает горячих в CRM.\n\nПодскажите, основной поток клиентов сейчас идет из Instagram или сразу в WhatsApp?"
"""

CONTEXT_RELEVANCE_GUARD_PROMPT = """Context relevance guardrail:
- Use facts from history or memory only when the current user message is about business fit, expected result, package selection, scope, price, checkout, call booking, or similar consultation.
- For introductory solution questions like "что такое ...", "объясните простыми словами", "как это работает", answer the concept in simple business language. Do not mention previous budget, CRM, niche, or old recommendations unless useful now.
- A short introductory solution answer may include one current diagnostic question when it naturally opens the sales consultation.
- Do not recommend a package, stack, integration scope, or timeline unless the current user explicitly asks about solution selection, implementation, what they need, or what to start with.
- Avoid the phrase "целевой вес". If a business follow-up is useful, ask where leads are currently lost or what process should be automated.
- Ask for business niche and sales channel together only when useful for the next consultation step. Do not turn the dialog into a form."""

FLOW_FLEXIBILITY_GUARD_PROMPT = """Adaptive flow guardrail:
- Do not run a hardcoded questionnaire or fixed funnel. There is no mandatory order of questions.
- Treat tenant prompts as business goals and product context, not as a rigid script.
- Any short or ambiguous user reply must be interpreted strictly as an answer to your immediately previous assistant message.
- It is categorically forbidden to attach ambiguous confirmations to older topics from previous context, such as portfolio, security, integrations, or explanations from several turns ago.
- If the client gives a vague answer to your previous qualifying question, do not ask the same question again.
- In vague-answer cases, acknowledge the intent, infer a reasonable commercial orientation from the available context, and move the conversation forward.
- Keep the goal stable: understand the business bottleneck, use RAG/context to suggest a relevant AI solution, and guide toward purchase, call booking, or checkout when the client is ready."""

ENGAGEMENT_GUARD_PROMPT = """Engagement guardrail:
- The bot's job is not only to inform. It should move the user into a practical expert consultation that can lead to purchase or a call.
- When the user asks a business result question like "will an agent work for me", "how fast can we launch", "will it increase sales", or "how much can it automate", do not answer like a dry article.
- Acknowledge the business goal in a grounded way. Do not promise a specific revenue result.
- Choose one natural next move: ask a useful question, offer a realistic implementation direction, or suggest the next commercial step from context.
- Do not cite generic market statistics unless the user asks for proof or cases.
- Use a calm expert consultant tone: practical, confident, and human.
- Sound like an AI architect who understands small and medium business operations, not a script.
- Speak in the client's result language: fewer missed leads, faster responses, cleaner CRM, automatic qualification, and simpler sales work.
- Do not ask multiple questions at once, except a compact pair like "ниша и основной канал заявок" when it is genuinely useful.
- Do not use medical or wellness phrasing.
- If the client answers vaguely to your previous question, never repeat that same question. Interpret the intent and move forward with an expert suggestion."""

CHECKOUT_CONTACT_VALIDATION_PROMPT = """Checkout contact validation guardrail:
- If a dialog ever enters a text data-collection step for name, business niche, website/social link, phone, or project details, never say "заявка оформлена", "передал менеджеру", "заявка принята", or similar until the current user message physically contains a phone-like number and at least one project detail.
- Words like "написал", "отправил", "лови", "да", "ок", empty confirmations, or any message without real contact data are not valid project data.
- If the client says they sent the contacts but the current message has no phone and project detail, repeat the request warmly instead of closing the request.
- Do not ask for contact data in ordinary checkout-card flow. Use this validation only if contact collection was already started in the chat or appears in the draft.
"""

CLIENT_FACING_PRIVACY_PROMPT = """Client-facing language guardrail:
- Never mention internal architecture or process terms to the client: RAG, prompt, context, model, router, fallback, backend, service, tenant, or system.
- If a draft contains those terms, rewrite them into normal human language or remove them.
"""

UNIFIED_COMMERCIAL_RULES_PROMPT = f"""ЕДИНЫЙ КОММЕРЧЕСКИЙ БЛОК AI-ДЕВЕЛОПМЕНТА:
1. ПРИОРИТЕТ БИЗНЕС-РЕЗУЛЬТАТА
- Главная задача - продать понятное внедрение: ИИ-агент, база знаний, умная воронка, авто-корзина или интеграция с CRM.
- Говори через пользу для бизнеса: меньше ручной переписки, быстрее ответы клиентам, меньше потерянных заявок, понятная квалификация, аккуратная передача в CRM.
- Портфолио, кейсы, безопасность, стек и процесс внедрения обсуждай по прямому вопросу клиента или когда это помогает снять сомнение.

2. PRICING / РАСЧЕТ ПРОЕКТА
- Не выдумывай цены, сроки, скидки и гарантии окупаемости.
- Используй цены и пакеты только из динамического контекста товаров/услуг, если backend их передал.
- Базовые офферы для ориентира без жестких цен: {BASE_ASSISTANT_OFFER_NAME}, {AUTO_CART_OFFER_NAME}, {AI_AGENT_IMPLEMENTATION_OFFER_NAME}.
- Если клиент просит стоимость, но данных недостаточно, коротко скажи: "Нужно быстро уточнить вводные, чтобы посчитать проект без выдуманных цифр."
- Для расчета обычно нужны: ниша, текущий канал заявок, CRM/таблица/сайт, что должно автоматизироваться, примерный объем обращений и желаемый срок запуска.

3. СКОУП БЕЗ ГАЛЛЮЦИНАЦИЙ
- Не обещай конкретный рост продаж, экономию часов или сроки запуска без данных.
- Если клиент не знает, что ему нужно, предложи простой первый шаг: аудит текущей воронки и выбор одной автоматизации с максимальным эффектом.
- Если клиент отвечает размыто, не повторяй анкету. Дай экспертную гипотезу и один следующий вопрос.
- Не дублируй все параметры клиента в клиентском тексте. Используй факты только для выбора решения и сразу предлагай следующий практический шаг.

4. VARIED CALL-TO-ACTIONS / ЖИВОЙ СТИЛЬ ВОПРОСОВ
- Разнообразь вопросы, закрывающие этап диалога. Не повторяй монотонный шаблон "Хотите, я рассчитаю/расскажу?".
- Задавай вопросы естественно, как живой опытный AI-архитектор и B2B-продавец.
- Не вставляй коммерческий CTA в каждое сообщение подряд. Если уже предлагал расчет, смени тактику: уточни канал заявок, CRM, объем ручной работы или главный узкий участок.
- Варианты для редкого уместного следующего шага: "Давайте прикинем, какая автоматизация даст быстрый эффект.", "Сначала разложим вашу воронку на 2-3 узких места.", "Можно начать с базового ассистента и дальше подключить CRM."
- Запрещено завершать сообщение фразой "Что скажете?", если она уже использовалась в последних 3 репликах ассистента.
- В каждом сообщении должна быть новизна и живой интерес к бизнес-задаче клиента.

5. МАТРИЦА ОТКАЗОВ
- Технический отказ: если клиент говорит "нет", "не надо" на предложение рассказать про архитектуру, безопасность, кейсы или стек, это не отказ от покупки. Зафиксируй отказ и вернись к бизнес-задаче.
- Коммерческий отказ: если клиент говорит "дорого", "подумаю", "не сейчас" на предложение внедрения или созвона, применяй связку: присоединение -> возврат к потере/узкому месту -> снижение барьера до аудита или минимального пилота.
- Никогда не повторяй прошлый вопрос или фразу слово в слово, даже если клиент отвечает односложно.

6. CHECKOUT / ЗАКРЫТИЕ СДЕЛКИ
- Если backend возвращает checkout-card flow, коротко подтверди выбранный оффер и верни управление backend. Карточку и кнопки оформляет клиент по ChatResponse.
- Если ответ идет обычным текстом и клиент уже согласился на расчет или заявку, можно запросить данные для проекта: имя, сфера бизнеса, ссылка на сайт/Instagram и телефон.
- Если диалог уже перешел в текстовый сбор контактов, не говори "заявка оформлена" или "передал менеджеру", пока клиент реально не написал телефон и хотя бы одну деталь проекта в текущем сообщении.
- Если клиент отвечает "написал", "отправил", "лови", "да" или другим пустым подтверждением без телефона и детали проекта, повторно попроси телефон и вводные по проекту.

7. ЗАПРОС КЕЙСОВ И ДЕМО
- Если клиент просит показать кейсы, портфолио, примеры работ или демонстрацию, вежливо отправь его на сайт/портфолио.
- Шаблон: "Кейсы, примеры работ и демо будут собраны на сайте: https://your-portfolio.dev/. Могу пока быстро сориентировать, какой сценарий подойдет под вашу воронку."
"""

OTHER_PLATFORM_GUARD_PROMPT = """ЧЕСТНЫЙ ОТКАЗ ПО ЧУЖИМ ПЛАТФОРМАМ:
- Если клиент спрашивает про чужой сервис, no-code платформу или готовый SaaS, не выдумывай внутренние условия, тарифы или ограничения этой платформы.
- Ответь открыто: "По чужим тарифам и внутренним ограничениям лучше свериться с их актуальными условиями. Я могу оценить, нужен ли вам готовый сервис или выгоднее собрать ИИ-агента под вашу воронку."
- Затем задай один практический вопрос по задаче клиента.
"""


SALES_MASTER_PROMPT = """Highest-priority sales behavior:
- You are not a passive FAQ bot. You are a strong AI architect and sales consultant who leads the client from interest to a practical project decision.
- Default shape: one very short practical answer plus one useful next move when it helps the sale.
- Keep answers maximally compressed. Usually 1-2 short sentences. Never write a long sentence just to satisfy a sentence limit.
- Do not ask permission with phrases like "хотите, я прикину", "могу подобрать", "вам прикинуть", or "нужно ли сравнить".
- Instead, take control with one concise next diagnostic question.
- The client often does not know what AI solution or package they need. Do not ask them to choose blindly. Diagnose their funnel, then guide them.
- For package, scope, timeline, or "what should I implement" questions, use the current context and ask only for the one missing detail that is truly needed, or propose a reasonable starting orientation when the client is unsure.
- Do not force a fixed question order. If the client answers vaguely, interpret their intent and keep moving instead of repeating the same question.
- Double-question ban: never offer two follow-up topics in one question. Offer exactly one next step at a time: architecture, cases/demo, project estimate, call booking, or checkout.
- Avoid dry phrases like "подберем индивидуально", "все зависит", or overloaded technical jargon unless the user explicitly asks for architecture detail.
- Avoid generic filler like "подбирается индивидуально", "зависит от многих факторов", or "нужно учитывать особенности". Replace it with a concrete next step.
- Do not dump all facts from RAG. Use only the one fact needed for the current sales step.
- Follow the sales stages by the meaning of the latest context, not by isolated keywords:
  1. Qualification: learn business niche, lead channel, CRM/website stack, and the bottleneck when needed.
  2. Consultation and comparison: when the client agrees to learn options, compare relevant service options such as Базовый ИИ-ассистент, Авто-корзина под ключ, and ИИ-агент под ключ. Do not output a product card/cart/checkout.
  3. Price presentation: only after the client agrees after comparison, present package prices or estimate ranges from dynamic product context.
  4. Checkout: only after the client agrees with the project/package, keep the text short and let backend generate the cart/product card or handoff.
- Any semantically affirmative reply to the previous stage question moves exactly one stage forward. If you just asked whether to show options, agreement means Stage 2 comparison, not checkout.
- In Stage 2, explain the practical difference between a lighter assistant, a smart-cart automation, and a deeper agent/integration when relevant. Do not name prices yet unless the sales stage instruction says Stage 3.
- Do not repeat the same value phrase across the dialog. Vary the reasoning or shorten it once the point has already been made.
- Do not present a bare package name and price. Business value and fit always come before price.
- Distinguish a refusal of a side topic from a refusal to buy. A side-topic refusal means return to the client's result; a purchase refusal means handle the objection professionally.
- Delivery boundary: do not promise exact revenue uplift, launch dates, or integrations without data. Frame it as scoping and recommend an audit/call for uncertain cases."""

SALES_REWRITE_SYSTEM_PROMPT = """Ты — главный редактор и эксперт по переписке для продажи AI-разработки и автоматизации.

Твоя единственная задача — взять черновик ответа AI-архитектора-продавца и переписать его так, чтобы он звучал на 100% как сообщение от живого, опытного консультанта.
Ты всегда оцениваешь черновик вместе с недавней историей сообщений, чтобы не допустить зацикливания, повторов и навязчивой продажи.

Rules:
- Return only the final Russian message for the client. No JSON, markdown, comments, explanations, system tags, or alternatives.
- Keep it maximally compressed: usually 1-2 short sentences.
- Answer the exact question using only facts already present in the draft/context.
- Use extremely simple business language by default. Do not sound technical unless the user explicitly asks for architecture.
- Ruthlessly humanize dry RAG/context language. If the draft contains overloaded technical phrases, rewrite them into clear business outcomes: faster replies, fewer missed leads, cleaner CRM, automatic qualification, and simpler sales work.
- If the draft talks about risks, data access, reliability, or security, explain it calmly. Do not add absolute guarantees that are not in the draft.
- Never promise guaranteed sales growth, exact ROI, or flawless operation.
- Ban overloaded phrases such as "оркестрация микросервисов", "векторные эмбеддинги", "инференс", "LLM пайплайн", unless the user asks for technical depth.
- Never mention internal terms to the client: RAG, промпт, контекст, модель, роутер, fallback, database, backend, service, tenant, or system.
- For "Что такое <solution>?", rewrite toward this style: "Это автоматизация, которая отвечает клиентам, квалифицирует заявки и передает горячие лиды в CRM. Сначала я бы посмотрел, где у вас сейчас теряются обращения."
- Move the client forward when useful: ask one relevant question, propose a realistic orientation, or suggest the next commercial action.
- Never ask combined/double questions. If you want to offer architecture and cases, choose one topic now and leave the other for later.
- Destroy repetitive sales scripts. If recent assistant messages already offered to calculate price/cost or the draft repeats a closing phrase like "Сориентировать по стоимости?", "Готовы оформить?", "Посчитаем?", remove or soften that question.
- Interpret short or ambiguous confirmations only as an answer to the latest assistant message. Never connect them to older topics from previous turns.
- If the client asks a content question like "А это безопасно?", "Как подключается CRM?" or "Сколько внедрять?", first give a warm expert answer and the business benefit. End with one organic question on the same topic, not about money.
- Do not ask permission with phrases like "хотите, я прикину", "могу подобрать", "вам прикинуть", "нужно ли сравнить".
- Do not ask the client to choose between packages when they do not know what they need. Use available context and give an expert orientation when the client is unsure.
- Ask for niche and main lead channel together when the current message is about solution selection, expected result, or "what should I implement". Do not ask for them on unrelated general explanations.
- If the current user message is a vague answer to your previous question, do not repeat that question. Acknowledge the vague answer and offer a practical next orientation based on available context.
- Separate any follow-up question from the main answer with a blank line (`\n\n`).
- Avoid dry phrases: "индивидуально", "зависит от многих факторов", "по best practices" without a concrete next step.
- Avoid generic filler like "подбирается индивидуально", "зависит от многих факторов", or "нужно учитывать особенности". Replace it with a concrete next step.
- Do not mention prices, payment, cart, call booking, or checkout unless the draft/current turn is semantically commercial in context, either by direct request or by confirming the latest assistant question about that commercial step.
- If mentioning price, use only prices from the dynamic product context.
- If the draft contains an unsupported price or project calculation, replace it with: "Нужно быстро уточнить вводные, чтобы посчитать проект без выдуманных цифр."
- Preserve the staged flow: Stage 2 compares solution options without card/checkout; Stage 3 presents prices/estimate; Stage 4 is the only stage where cart/card/checkout/call handoff can appear.
- If the latest user message is an affirmative answer to "show options" or "which solution fits", do not rewrite the answer into a bare package+price or checkout card intro. It must be a comparison with a reasoned recommendation.
- Data invariants: never change factual values from the draft/context: prices, package names, implementation scope, CRM names, deadlines, or client constraints.
- Do not add delivery certainty. Do not promise a specific revenue result.
- For security, privacy, data-access, platform-risk, or reliability questions, answer the concern instead of pushing purchase.
- Strict checkout check: if the draft tries to close the request with phrases like "Заявка оформлена", "Передаю менеджеру", "Заявка принята", but the latest user message does not physically contain a phone-like number and at least one project detail, the draft is lying. Rewrite it into a polite stop message asking for the phone and project details directly in chat.

Good target style: short exact answer plus one adaptive next move when useful.
"""

ROLEPLAY_DEMO_SYSTEM_PROMPT = """You are running a live sales roleplay demo for the user's requested niche.

This mode is isolated from Plum Dev sales.
Do not sell AI agents, automation, audits, checkout products, CRM handoff, implementation packages, or Plum Dev services.
Do not use RAG, tenant commercial context, previous AI-service offers, or AI-agent prices.
Stay inside the requested seller role until the user clearly exits the demo.
If a demo file/context is provided, use only facts from that file/context for concrete prices, terms, product specs, availability, delivery, guarantees, and conditions. Do not invent missing facts.
If no demo file/context is provided, you may improvise from general knowledge, but be transparent that a file or catalog would make the demo more exact.
If the user switches niche with a short phrase such as "а теперь продавца пептидов", treat it as a new roleplay request.
If the requested niche involves health, supplements, peptides, medication, or weight loss, keep claims cautious: do not promise treatment, guaranteed weight loss, diagnosis, dosage, or medical safety. Suggest checking contraindications with a doctor when relevant.
Answer in Russian, briefly, as the seller in that niche."""


CRITICAL_COMMERCIAL_TRIGGER_RULE = (
    "КРИТИЧЕСКОЕ ПРАВИЛО: веди диалог как живой опытный B2B-продавец, а не как анкета. "
    "Запрещены жесткие сценарии вида 'сначала спроси А, потом Б, затем В'. "
    "Ориентируйся на общую коммерческую цель: понять проблему клиента, дать релевантное решение из RAG/контекста "
    "и мягко продвинуть к покупке или следующему логичному действию. "
    "Если клиент интересуется ценой, сроком внедрения, интеграциями или составом решения, возьми точные данные из RAG-контекста, "
    "ответь по сути и выбери один уместный следующий вопрос или рекомендацию. "
    "Если нужны ниша и канал заявок, спрашивай их вместе, но не превращай диалог в обязательную анкету."
    "\n\nГИБКОСТЬ В ДИАЛОГЕ: Если ты задаешь клиенту квалифицирующий вопрос "
    "(про нишу, канал заявок, CRM, бюджет или пожелания), а клиент отвечает размыто "
    "('не знаю', 'на твой выбор', 'сделайте как лучше'), тебе КАТЕГОРИЧЕСКИ "
    "ЗАПРЕЩЕНО повторять свой вопрос заново. Вместо этого прояви экспертную инициативу: "
    "поддержи клиента, предложи понятный стартовый сценарий или готовое решение на основе уже собранных параметров "
    "и продвинь диалог к следующему коммерческому шагу. Если у клиента нет четкого ТЗ, начни с простой гипотезы: "
    "сначала автоматизировать прием и квалификацию заявок, затем подключить CRM/таблицу и авто-корзину. "
    "Если не уверен в расчете, убери цифры и предложи быстрый аудит воронки. Никогда не создавай тупик повтором одного и того же вопроса."
)


NO_REPEAT_RULE = (
    "ЗАПРЕТ НА ПОВТОРЫ: Тебе строго запрещено отправлять один и тот же текст "
    "или одну и ту же рекомендацию два раза подряд. Если клиент ответил на твой "
    "вопрос, зафиксируй его ответ, поддержи его мотивацию и двигайся дальше по "
    "воронке к следующему логичному шагу. Не повторяй прошлые реплики."
)


def is_retryable_gemini_unavailable(exc: BaseException) -> bool:
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, BaseException) and is_retryable_gemini_unavailable(cause):
        return True

    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    status = str(getattr(exc, "status", "") or getattr(exc, "reason", "")).upper()
    message = str(exc).upper()
    return (
        status_code == 503
        or "503" in message
        or "UNAVAILABLE" in status
        or "UNAVAILABLE" in message
    )


class GeminiService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_keys = list(settings.gemini_api_keys)
        self.clients = {
            api_key.name: genai.Client(api_key=api_key.value)
            for api_key in settings.gemini_api_keys
        }
        self.quota = GeminiQuotaManager(settings.gemini_api_keys)
        self._active_key_index = 0
        self._key_lock = Lock()

    async def classify_routes(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        system_prompt: str = "",
        client_facts: dict[str, object] | None = None,
    ) -> list[Route]:
        heuristic_routes = self._heuristic_routes(message)
        if not self.settings.use_gemini_router or heuristic_routes != [Route.general]:
            return heuristic_routes

        prompt = self._format_router_prompt(message, chat_history, client_facts)
        try:
            text = await self._generate_text(
                model=self.settings.router_model,
                model_pool=self.settings.router_model_pool,
                prompt=prompt,
                system_instruction=self._ensure_exit_roleplay_router_rule(
                    self._resolve_system_prompt(
                        system_prompt,
                        ROUTER_SYSTEM_PROMPT,
                    )
                ),
                temperature=0,
                max_output_tokens=64,
            )
        except Exception as exc:
            if self._is_quota_or_rate_limit_error(exc):
                logger.warning(
                    "Gemini router quota/rate limit reached; falling back to heuristic routes"
                )
            else:
                logger.exception("Gemini router failed; falling back to heuristic routes")
            return self._heuristic_routes(message)

        return self._parse_routes(text, fallback_routes=heuristic_routes)

    async def classify_route(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        system_prompt: str = "",
    ) -> Route:
        return (await self.classify_routes(message, chat_history, system_prompt))[0]

    async def classify_sales_stage_transition(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> dict[str, object]:
        prompt = self._format_sales_stage_router_prompt(
            message,
            chat_history,
            client_facts,
        )
        try:
            text = await self._generate_text(
                model=self.settings.router_model,
                model_pool=self.settings.router_model_pool,
                prompt=prompt,
                system_instruction=SALES_STAGE_ROUTER_PROMPT,
                temperature=0,
                max_output_tokens=96,
            )
        except Exception as exc:
            if self._is_quota_or_rate_limit_error(exc):
                logger.warning(
                    "Gemini sales-stage router quota/rate limit reached; no stage transition"
                )
            else:
                logger.exception("Gemini sales-stage router failed; no stage transition")
            return {
                "stage": "none",
                "commercial_intent": False,
                "checkout_intent": False,
            }

        return self._parse_sales_stage_transition(text)

    async def classify_content_followup(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        previous_assistant = self._last_assistant_message(chat_history) or ""
        if "?" not in previous_assistant:
            return "none"

        prompt = self._format_content_followup_router_prompt(
            message,
            chat_history,
            client_facts,
        )
        try:
            text = await self._generate_text(
                model=self.settings.router_model,
                model_pool=self.settings.router_model_pool,
                prompt=prompt,
                system_instruction=CONTENT_FOLLOWUP_ROUTER_PROMPT,
                temperature=0,
                max_output_tokens=64,
            )
        except Exception as exc:
            if self._is_quota_or_rate_limit_error(exc):
                logger.warning(
                    "Gemini content-followup router quota/rate limit reached; no content follow-up"
                )
            else:
                logger.exception("Gemini content-followup router failed; no content follow-up")
            return "none"

        return self._parse_content_followup(text)

    async def answer_general(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        system_prompt: str = "",
    ) -> str:
        prompt = self._format_chat_prompt(message, chat_history)
        return await self._generate_text(
            model=self.settings.general_model,
            model_pool=self.settings.general_model_pool,
            prompt=prompt,
            system_instruction=self._resolve_system_prompt(
                system_prompt,
                GENERAL_SYSTEM_PROMPT,
            ),
            temperature=0.4,
            max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
        )

    async def rewrite_query_hyde(
        self,
        text: str,
        system_prompt: str = "",
    ) -> str:
        normalized_text = text.strip()
        if not normalized_text:
            return normalized_text

        prompt = "\n".join(
            [
                "Original user message:",
                normalized_text,
                "",
                "Rewrite it as an optimized hybrid retrieval query plus a compact hypothetical answer fragment.",
            ]
        )

        try:
            rewritten = await self._generate_text(
                model=self.settings.router_model,
                model_pool=self.settings.router_model_pool,
                prompt=prompt,
                system_instruction=self._resolve_system_prompt(
                    system_prompt,
                    HYDE_SYSTEM_PROMPT,
                ),
                temperature=0.2,
                max_output_tokens=256,
            )
        except Exception as exc:
            if self._is_quota_or_rate_limit_error(exc):
                logger.warning(
                    "HyDE query rewrite quota/rate limit reached; falling back to original message"
                )
            else:
                logger.exception(
                    "HyDE query rewrite failed; falling back to original message"
                )
            return normalized_text

        rewritten = rewritten.strip()
        if not rewritten:
            return normalized_text

        return rewritten

    async def answer_with_rag(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        rag_context: str,
        commercial_context: str = "",
        memory_context: str = "",
        response_instruction: str = "",
        system_prompt_addon: str = "",
        final_system_prompt: str = "",
        client_facts: dict[str, object] | None = None,
    ) -> str:
        roleplay_mode = self._is_roleplay_demo_instruction(response_instruction)
        prompt = "\n\n".join(
            [
                self._format_chat_prompt(message, chat_history, client_facts),
                "Long-term B2B memory context:",
                (
                    "Контекст прошлых этапов общения с этим B2B-клиентом: "
                    f"{memory_context}. Используй его, чтобы продолжить переговоры с нужной точки."
                    if memory_context
                    else "No long-term memory context was provided."
                ),
                "Supabase knowledge-base context:",
                rag_context or "No relevant RAG context was provided.",
                "Commercial tenant context:",
                commercial_context or "No commercial context was provided.",
                "Response instruction:",
                response_instruction or "No extra response instruction.",
                "Answer in Russian using only the relevant context above.",
            ]
        )
        if roleplay_mode:
            system_instruction = "\n\n".join(
                [
                    ROLEPLAY_DEMO_SYSTEM_PROMPT,
                    response_instruction,
                ]
            )
            return (
                await self._generate_text(
                    model=self.settings.general_model,
                    model_pool=self.settings.general_model_pool,
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.2,
                    max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
                )
            ).strip()

        base_system_prompt = self._resolve_system_prompt(
            final_system_prompt,
            FINAL_SYSTEM_PROMPT,
        )
        system_instruction = "\n\n".join(
            [
                SALES_MASTER_PROMPT,
                base_system_prompt,
                COMMERCIAL_GUARD_PROMPT,
                STYLE_GUARD_PROMPT,
                CONTEXT_RELEVANCE_GUARD_PROMPT,
                FLOW_FLEXIBILITY_GUARD_PROMPT,
                ENGAGEMENT_GUARD_PROMPT,
                CHECKOUT_CONTACT_VALIDATION_PROMPT,
                CLIENT_FACING_PRIVACY_PROMPT,
                UNIFIED_COMMERCIAL_RULES_PROMPT,
                OTHER_PLATFORM_GUARD_PROMPT,
            ]
        )
        system_instruction = self._ensure_critical_commercial_trigger_rule(
            system_instruction
        )
        if response_instruction:
            system_instruction = "\n\n".join(
                [
                    system_instruction,
                    "Current-turn response instruction. This overrides generic style rules when they conflict:",
                    response_instruction,
                ]
            )
        tenant_prompt_addon = self._sanitize_prompt_checkout_rules(
            self._sanitize_prompt_flow_rules(system_prompt_addon)
        )
        if tenant_prompt_addon:
            system_instruction = "\n\n".join(
                [
                    system_instruction,
                    "Tenant-specific instructions:",
                    tenant_prompt_addon,
                ]
            )
            system_instruction = self._ensure_critical_commercial_trigger_rule(
                system_instruction
            )

        draft_answer = await self._generate_text(
            model=self.settings.rag_model,
            model_pool=self.settings.rag_model_pool,
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.2,
            max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
        )
        final_answer = await self._rewrite_sales_answer(
            message=message,
            chat_history=chat_history,
            draft_answer=draft_answer,
            rag_context=rag_context,
            commercial_context=commercial_context,
            response_instruction=response_instruction,
            final_system_prompt=final_system_prompt,
            client_facts=client_facts,
        )
        final_answer = await self._avoid_repeated_answer(
            message=message,
            chat_history=chat_history,
            answer=final_answer,
            rag_context=rag_context,
            commercial_context=commercial_context,
            response_instruction=response_instruction,
            client_facts=client_facts,
        )
        final_answer = self._avoid_repeated_closing_phrase(final_answer, chat_history)
        final_answer = self._remove_repeated_commercial_closing_question(
            final_answer,
            chat_history,
        )
        final_answer = self._remove_stale_or_repeated_question(
            final_answer,
            chat_history,
            client_facts,
        )
        final_answer = self._soften_absolute_sales_guarantees(final_answer)
        return self._ensure_followup_question_spacing(final_answer)

    async def extract_roleplay_context_from_attachment(
        self,
        *,
        message: str,
        topic: str,
        attachments: list[ChatAttachment],
    ) -> str:
        prompt = "\n\n".join(
            [
                "Analyze the attached demo file for a sales roleplay.",
                f"Requested roleplay niche/product: {topic or 'infer from file and user message'}",
                f"User message/caption: {message or 'No caption provided.'}",
                (
                    "Extract only concrete facts visible in the file: products, prices, packages, specs, terms, "
                    "delivery/payment conditions, objections that can be answered, and claims that are safe to use. "
                    "Do not invent missing facts. If the file is an image, read visible text and infer only obvious table/catalog structure. "
                    "Return a compact Russian fact sheet for a seller roleplay. No markdown table is needed."
                ),
            ]
        )
        return await self._generate_multimodal_text(
            model=self.settings.general_model,
            model_pool=self.settings.general_model_pool,
            prompt=prompt,
            system_instruction=(
                "You extract temporary sales-demo context from user-provided files. "
                "The extracted facts are session-local and must not be treated as tenant knowledge base."
            ),
            attachments=attachments,
            temperature=0,
            max_output_tokens=768,
        )

    async def answer_roleplay_with_demo_context(
        self,
        *,
        message: str,
        chat_history: list[ChatHistoryMessage],
        topic: str,
        demo_context: str,
        no_file_fallback: bool = False,
    ) -> str:
        fallback_note = (
            "No file was provided. Start the demo anyway, but briefly say that with a price/catalog file the answer would be more exact."
            if no_file_fallback
            else "Use the demo file context as the source of concrete facts."
        )
        prompt = "\n\n".join(
            [
                self._format_chat_prompt(message, chat_history),
                f"Current demo niche/product: {topic or 'infer from recent messages'}.",
                "Temporary demo file/context:",
                demo_context or "No file context was provided.",
                fallback_note,
                "Start or continue the roleplay as the seller in this niche. Answer the user's latest message inside the role.",
            ]
        )
        answer = await self._generate_text(
            model=self.settings.general_model,
            model_pool=self.settings.general_model_pool,
            prompt=prompt,
            system_instruction=ROLEPLAY_DEMO_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
        )
        return self._ensure_followup_question_spacing(answer.strip())

    async def _rewrite_sales_answer(
        self,
        *,
        message: str,
        chat_history: list[ChatHistoryMessage],
        draft_answer: str,
        rag_context: str,
        commercial_context: str,
        response_instruction: str = "",
        final_system_prompt: str = "",
        client_facts: dict[str, object] | None = None,
    ) -> str:
        if self._is_roleplay_demo_instruction(response_instruction):
            return draft_answer

        prompt = "\n\n".join(
            [
                "Conversation state:",
                self._format_conversation_state(chat_history, message, client_facts),
                "Persistent client facts:",
                self._format_collected_facts(chat_history, client_facts),
                "Recent chat history:",
                self._format_history(
                    chat_history,
                    limit=self.settings.max_history_messages,
                ),
                "Current user message:",
                message,
                "Draft answer:",
                draft_answer,
                "RAG context was provided:",
                "yes" if rag_context else "no",
                "Commercial context was provided:",
                "yes" if commercial_context else "no",
                "Response instruction:",
                response_instruction or "No extra response instruction.",
                "Rewrite the draft into the final sales-consultant message.",
            ]
        )
        try:
            base_system_prompt = self._resolve_system_prompt(
                final_system_prompt,
                FINAL_SYSTEM_PROMPT,
            )
            rewritten = await self._generate_text(
                model=self.settings.general_model,
                model_pool=self.settings.general_model_pool,
                prompt=prompt,
                system_instruction="\n\n".join(
                    [
                        self._ensure_critical_commercial_trigger_rule(
                            SALES_REWRITE_SYSTEM_PROMPT
                        ),
                        base_system_prompt,
                        STYLE_GUARD_PROMPT,
                        CONTEXT_RELEVANCE_GUARD_PROMPT,
                        FLOW_FLEXIBILITY_GUARD_PROMPT,
                        ENGAGEMENT_GUARD_PROMPT,
                        CHECKOUT_CONTACT_VALIDATION_PROMPT,
                        CLIENT_FACING_PRIVACY_PROMPT,
                        UNIFIED_COMMERCIAL_RULES_PROMPT,
                        OTHER_PLATFORM_GUARD_PROMPT,
                        (
                            "Current-turn response instruction. This overrides generic style rules when they conflict:\n"
                            f"{response_instruction}"
                            if response_instruction
                            else ""
                        ),
                    ]
                ),
                temperature=0.1,
                max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
            )
        except Exception as exc:
            if self._is_quota_or_rate_limit_error(exc):
                logger.warning(
                    "Gemini sales rewrite quota/rate limit reached after trying all keys"
                )
                raise
            else:
                logger.exception("Gemini sales rewrite failed; using draft answer")
            return draft_answer

        return rewritten.strip() or draft_answer

    async def summarize_b2b_memory(
        self,
        dialog: str,
        existing_summary: str = "",
        system_prompt: str = "",
    ) -> str:
        prompt = "\n\n".join(
            [
                "Existing long-term memory:",
                existing_summary or "No existing memory.",
                "Current session dialog:",
                dialog or "No dialog.",
                (
                    "Прочитай этот диалог. Выдели главное для B2B-сделки: "
                    "какой продукт интересует клиента, какой объем или формат он "
                    "обсуждает, какие условия или скидки запрашивает. Напиши "
                    "сухой итог в 2-4 предложениях для долгосрочной памяти системы."
                ),
            ]
        )
        return await self._generate_text(
            model=self.settings.router_model,
            model_pool=self.settings.router_model_pool,
            prompt=prompt,
            system_instruction=self._resolve_system_prompt(
                system_prompt,
                MEMORY_SUMMARY_SYSTEM_PROMPT,
            ),
            temperature=0.2,
            max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
        )

    @retry(
        retry=retry_if_exception(is_retryable_gemini_unavailable),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_embedding(self, text: str) -> list[float]:
        normalized_text = text.strip()
        if not normalized_text:
            raise RuntimeError("Cannot create embedding for empty text")

        def call_model() -> list[float]:
            estimated_tokens = estimate_embedding_tokens(normalized_text)
            skipped: set[tuple[str, str]] = set()
            last_exc: BaseException | None = None
            max_attempts = (
                len(self.settings.gemini_api_keys)
                * len(self.settings.embedding_model_pool)
            )

            for _ in range(max(1, max_attempts)):
                lease: GeminiQuotaLease | None = None
                try:
                    lease = self.quota.reserve(
                        self.settings.embedding_model_pool,
                        estimated_tokens,
                        skipped=skipped,
                    )
                    response = self._embed_content(
                        lease.model,
                        lease.key_name,
                        normalized_text,
                        task_type="retrieval_query",
                    )
                    values = response
                    if not values:
                        raise RuntimeError(
                            f"Embedding model {lease.model} returned no vectors"
                        )

                    if len(values) != 768:
                        logger.warning(
                            "Unexpected embedding dimension from %s: %s",
                            lease.model,
                            len(values),
                        )

                    self.quota.complete(lease, estimated_tokens)
                    logger.debug(
                        "Gemini embedding used model=%s key=%s",
                        lease.model,
                        lease.key_name,
                    )
                    return list(values)
                except GeminiQuotaExhausted as exc:
                    if last_exc is not None:
                        raise RuntimeError(
                            "All Gemini embedding fallbacks failed before a quota slot opened"
                        ) from last_exc
                    raise RuntimeError(str(exc)) from exc
                except Exception as exc:
                    last_exc = exc
                    if lease is not None:
                        self.quota.refund(lease)
                        self.quota.cool_down(lease, exc)
                        skipped.add((lease.key_name, normalize_model_name(lease.model)))
                        logger.warning(
                            "Gemini embedding failed for model=%s key=%s; trying fallback: %s",
                            lease.model,
                            lease.key_name,
                            exc,
                        )
                    else:
                        raise

            raise RuntimeError(
                f"Gemini API error for embedding models {self.settings.embedding_model_pool}: {last_exc}"
            ) from last_exc

        return await asyncio.to_thread(call_model)

    @staticmethod
    def _embedding_model_name(model: str) -> str:
        if model.startswith("models/"):
            return model
        return f"models/{model}"

    def _embed_content(
        self,
        model: str,
        key_name: str,
        text: str,
        *,
        task_type: str,
    ) -> list[float]:
        model_name = self._embedding_model_name(model)
        response = self.clients[key_name].models.embed_content(
            model=model_name,
            contents=text,
            config=types.EmbedContentConfig(
                taskType=task_type,
                outputDimensionality=768,
            ),
        )
        if not response.embeddings:
            return []

        return list(response.embeddings[0].values or [])

    @staticmethod
    def _resolve_system_prompt(candidate: str, fallback: str) -> str:
        normalized_candidate = GeminiService._sanitize_prompt_flow_rules(candidate)
        normalized_candidate = GeminiService._sanitize_prompt_checkout_rules(
            normalized_candidate
        )
        return normalized_candidate or fallback

    @staticmethod
    def _ensure_exit_roleplay_router_rule(system_prompt: str) -> str:
        if "EXIT_ROLEPLAY" in (system_prompt or ""):
            return system_prompt
        return "\n\n".join([system_prompt.rstrip(), EXIT_ROLEPLAY_ROUTER_RULE])

    @staticmethod
    def _sanitize_prompt_flow_rules(prompt: str) -> str:
        normalized_prompt = (prompt or "").strip()
        if not normalized_prompt:
            return ""

        rigid_flow_patterns = (
            r"\bstep\s*\d+\b",
            r"\bstage\s*\d+\b",
            r"\bfirst\b.*\bthen\b",
            r"\bthen\b.*\bafter\b",
            r"\bask\s+.*\bthen\s+ask\b",
            r"шаг\s*\d+",
            r"этап\s*\d+",
            r"сначала\b.*\bпотом\b",
            r"сначала\b.*\bзатем\b",
            r"потом\b.*\bпосле\b",
            r"спроси\b.*\bпотом\s+спроси\b",
        )

        lines: list[str] = []
        for line in normalized_prompt.splitlines():
            normalized_line = line.strip().casefold()
            if any(re.search(pattern, normalized_line) for pattern in rigid_flow_patterns):
                continue
            lines.append(line)

        return "\n".join(lines).strip()

    @staticmethod
    def _sanitize_prompt_checkout_rules(prompt: str) -> str:
        normalized_prompt = (prompt or "").strip()
        if not normalized_prompt:
            return ""

        legacy_checkout_patterns = (
            r"42\s*000",
            r"49\s*500",
            r"strict\s+price",
            r"price\s+list",
            r"ФИО",
            r"full\s+name",
            r"delivery\s+(?:city|address)",
        )

        lines: list[str] = []
        for line in normalized_prompt.splitlines():
            normalized_line = line.strip().casefold()
            if any(re.search(pattern, normalized_line) for pattern in legacy_checkout_patterns):
                continue
            lines.append(line)

        return "\n".join(lines).strip()

    @staticmethod
    def _ensure_critical_commercial_trigger_rule(system_prompt: str) -> str:
        rules = []
        if CRITICAL_COMMERCIAL_TRIGGER_RULE not in system_prompt:
            rules.append(CRITICAL_COMMERCIAL_TRIGGER_RULE)
        if NO_REPEAT_RULE not in system_prompt:
            rules.append(NO_REPEAT_RULE)
        if UNIFIED_COMMERCIAL_RULES_PROMPT not in system_prompt:
            rules.append(UNIFIED_COMMERCIAL_RULES_PROMPT)
        if OTHER_PLATFORM_GUARD_PROMPT not in system_prompt:
            rules.append(OTHER_PLATFORM_GUARD_PROMPT)
        if not rules:
            return system_prompt

        return "\n\n".join(
            [
                system_prompt.rstrip(),
                "ЗАПРЕТЫ / ИНСТРУКЦИИ:",
                *rules,
            ]
        )

    @staticmethod
    def _is_roleplay_demo_instruction(response_instruction: str) -> bool:
        return "ROLEPLAY DEMO MODE IS ACTIVE" in (response_instruction or "")

    async def _avoid_repeated_answer(
        self,
        *,
        message: str,
        chat_history: list[ChatHistoryMessage],
        answer: str,
        rag_context: str,
        commercial_context: str,
        response_instruction: str = "",
        client_facts: dict[str, object] | None = None,
    ) -> str:
        previous_assistant = self._last_assistant_message(chat_history)
        if not previous_assistant:
            return answer
        if not self._is_repeated_answer(previous_assistant, answer):
            return answer

        prompt = "\n\n".join(
            [
                "Conversation state:",
                self._format_conversation_state(chat_history, message, client_facts),
                "Persistent client facts:",
                self._format_collected_facts(chat_history, client_facts),
                "Recent chat history:",
                self._format_history(
                    chat_history,
                    limit=self.settings.max_history_messages,
                ),
                "Current user message:",
                message,
                "Rejected repeated answer:",
                answer,
                "RAG context was provided:",
                "yes" if rag_context else "no",
                "Commercial context was provided:",
                "yes" if commercial_context else "no",
                "Response instruction:",
                response_instruction or "No extra response instruction.",
                "Write a new non-repeating answer that acknowledges the user's latest message and moves the conversation forward.",
            ]
        )
        try:
            rewritten = await self._generate_text(
                model=self.settings.general_model,
                model_pool=self.settings.general_model_pool,
                prompt=prompt,
                system_instruction="\n\n".join(
                    [
                        self._ensure_critical_commercial_trigger_rule(
                            SALES_REWRITE_SYSTEM_PROMPT
                        ),
                        STYLE_GUARD_PROMPT,
                        CONTEXT_RELEVANCE_GUARD_PROMPT,
                        FLOW_FLEXIBILITY_GUARD_PROMPT,
                        ENGAGEMENT_GUARD_PROMPT,
                        CHECKOUT_CONTACT_VALIDATION_PROMPT,
                        CLIENT_FACING_PRIVACY_PROMPT,
                        UNIFIED_COMMERCIAL_RULES_PROMPT,
                        OTHER_PLATFORM_GUARD_PROMPT,
                        (
                            "Current-turn response instruction. This overrides generic style rules when they conflict:\n"
                            f"{response_instruction}"
                            if response_instruction
                            else ""
                        ),
                    ]
                ),
                temperature=0.2,
                max_output_tokens=ECONOMY_MAX_OUTPUT_TOKENS,
            )
        except Exception:
            logger.exception("Failed to rewrite repeated answer; returning original")
            return answer

        if self._is_repeated_answer(previous_assistant, rewritten):
            return answer

        return rewritten.strip() or answer

    @classmethod
    def _avoid_repeated_closing_phrase(
        cls,
        answer: str,
        chat_history: list[ChatHistoryMessage],
    ) -> str:
        stripped = answer.rstrip()
        if not re.search(r"что\s+скажете\?\s*$", stripped, re.IGNORECASE):
            return answer

        recent_assistant = [
            item.content for item in chat_history if item.role == "assistant"
        ][-3:]
        if not any("что скажете?" in item.casefold() for item in recent_assistant):
            return answer

        alternatives = (
            "Как вам такой вариант?",
            "Начнем с базового ассистента?",
            "Соберем быстрый расчет проекта?",
        )
        used_text = " ".join(recent_assistant).casefold()
        replacement = next(
            (
                alternative
                for alternative in alternatives
                if alternative.casefold() not in used_text
            ),
            alternatives[0],
        )
        return re.sub(
            r"что\s+скажете\?\s*$",
            replacement,
            stripped,
            flags=re.IGNORECASE,
        )

    @classmethod
    def _remove_repeated_commercial_closing_question(
        cls,
        answer: str,
        chat_history: list[ChatHistoryMessage],
    ) -> str:
        recent_assistant = [
            item.content for item in chat_history if item.role == "assistant"
        ][-2:]
        if not recent_assistant:
            return answer

        if not any(cls._has_commercial_cta_marker(item) for item in recent_assistant):
            return answer

        stripped = answer.rstrip()
        match = re.search(r"(?P<prefix>.*?)(?P<question>[^.!?\n]*\?)\s*$", stripped, re.DOTALL)
        if not match:
            return answer

        closing_question = match.group("question").strip()
        if not cls._has_commercial_cta_marker(closing_question):
            return answer

        prefix = match.group("prefix").rstrip()
        replacement = cls._select_neutral_followup(recent_assistant)
        if not prefix:
            return replacement

        separator = "\n\n" if "\n\n" not in prefix[-4:] else "\n"
        return f"{prefix}{separator}{replacement}"

    @classmethod
    def _remove_stale_or_repeated_question(
        cls,
        answer: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        stripped = answer.rstrip()
        match = re.search(r"(?P<prefix>.*?)(?P<question>[^.!?\n]*\?)\s*$", stripped, re.DOTALL)
        if not match:
            return answer

        closing_question = match.group("question").strip()
        if not closing_question:
            return answer

        normalized_question = closing_question.casefold().replace("ё", "е")
        facts = client_facts or {}
        lead_channel_known = bool(str(facts.get("lead_channel") or "").strip())
        if lead_channel_known and (
            re.search(r"где.{0,40}теря.{0,40}заяв", normalized_question)
            or re.search(r"канал.{0,40}(заяв|клиент|привлеч)", normalized_question)
        ):
            return match.group("prefix").rstrip()

        recent_questions: list[str] = []
        for item in chat_history[-8:]:
            if item.role != "assistant":
                continue
            recent_questions.extend(
                question.strip()
                for question in re.findall(r"[^.!?\n]*\?", item.content)
                if question.strip()
            )

        normalized_closing = cls._normalize_for_repeat_check(closing_question)
        for previous_question in recent_questions:
            normalized_previous = cls._normalize_for_repeat_check(previous_question)
            if not normalized_previous:
                continue
            if normalized_previous == normalized_closing:
                return match.group("prefix").rstrip()
            if (
                min(len(normalized_previous), len(normalized_closing)) >= 35
                and difflib.SequenceMatcher(
                    None,
                    normalized_previous,
                    normalized_closing,
                ).ratio()
                >= 0.82
            ):
                return match.group("prefix").rstrip()

        return answer

    @staticmethod
    def _soften_absolute_sales_guarantees(answer: str) -> str:
        softened = re.sub(
            r"так что\s+ни\s+одна\s+заявка\s+не\s+потеряется",
            "это снижает риск потерянных заявок",
            answer,
            flags=re.IGNORECASE,
        )
        softened = re.sub(
            r"гарантирует,\s+что\s+ни\s+од(?:ин|на)\s+(?:клиент|заявка)[^.?!]*(?:не\s+будет\s+упущен[а]?|не\s+потеряется)",
            "помогает снизить риск пропущенных обращений",
            softened,
            flags=re.IGNORECASE,
        )
        softened = re.sub(
            r"\bни\s+од(?:ин|на)\s+(?:клиент|заявка)\s+не\s+(?:будет\s+)?(?:упущен[а]?|потеряется)",
            "меньше обращений будет теряться",
            softened,
            flags=re.IGNORECASE,
        )
        return softened

    @staticmethod
    def _has_commercial_cta_marker(text: str) -> bool:
        normalized = text.casefold()
        markers = (
            "стоимост",
            "цен",
            "прайс",
            "оформ",
            "расчет",
            "рассчет",
            "рассчит",
            "посчит",
            "купи",
            "купить",
            "заказ",
            "оплат",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _select_neutral_followup(recent_assistant: list[str]) -> str:
        used_text = " ".join(recent_assistant).casefold()
        alternatives = (
            "Что обычно спрашивают клиенты перед тем, как замолчать?",
            "Вы условия текстом скидываете или голосом?",
        )
        return next(
            (
                alternative
                for alternative in alternatives
                if alternative.casefold() not in used_text
            ),
            alternatives[0],
        )

    @staticmethod
    def _last_assistant_message(chat_history: list[ChatHistoryMessage]) -> str:
        for item in reversed(chat_history):
            if item.role == "assistant":
                return item.content
        return ""

    @staticmethod
    def _normalize_for_repeat_check(text: str) -> str:
        return " ".join(text.casefold().split())

    @classmethod
    def _is_repeated_answer(cls, previous: str, current: str) -> bool:
        normalized_previous = cls._normalize_for_repeat_check(previous)
        normalized_current = cls._normalize_for_repeat_check(current)
        if not normalized_previous or not normalized_current:
            return False
        if normalized_previous == normalized_current:
            return True
        if (
            min(len(normalized_previous), len(normalized_current)) >= 80
            and (
                normalized_previous in normalized_current
                or normalized_current in normalized_previous
            )
        ):
            return True

        return (
            difflib.SequenceMatcher(
                None,
                normalized_previous,
                normalized_current,
            ).ratio()
            >= 0.88
        )

    @retry(
        retry=retry_if_exception(is_retryable_gemini_unavailable),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _generate_text(
        self,
        *,
        model: str,
        model_pool: tuple[str, ...] | None = None,
        prompt: str,
        system_instruction: str,
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> str:
        def call_model() -> str:
            base_max_output_tokens = (
                max_output_tokens
                if max_output_tokens is not None
                else ECONOMY_MAX_OUTPUT_TOKENS
            )
            output_token_budgets = [base_max_output_tokens]
            if base_max_output_tokens < COMPLETION_RETRY_MAX_OUTPUT_TOKENS:
                output_token_budgets.append(COMPLETION_RETRY_MAX_OUTPUT_TOKENS)

            candidates = model_pool or (model,)
            last_exc: BaseException | None = None
            local_limit_errors: list[BaseException] = []

            for output_token_budget in output_token_budgets:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=output_token_budget,
                )
                estimated_tokens = estimate_tokens(
                    prompt,
                    system_instruction,
                    max_output_tokens=output_token_budget,
                )

                for candidate_model in candidates:
                    key_order = self._ordered_api_keys()
                    for api_key in key_order:
                        lease: GeminiQuotaLease | None = None
                        try:
                            lease = self.quota.reserve_for_key(
                                key_name=api_key.name,
                                model=candidate_model,
                                estimated_tokens=estimated_tokens,
                            )
                        except GeminiQuotaExhausted as exc:
                            local_limit_errors.append(exc)
                            self._advance_active_key(api_key.name)
                            next_key = self._next_key_name(api_key.name)
                            logger.info(
                                "Ключ %s исчерпан локальным quota guard для model=%s. Переключаюсь на ключ %s... %s",
                                api_key.name,
                                candidate_model,
                                next_key or "недоступен",
                                exc,
                            )
                            continue

                        try:
                            response = self.clients[api_key.name].models.generate_content(
                                model=candidate_model,
                                contents=prompt,
                                config=config,
                            )
                        except Exception as exc:
                            last_exc = exc
                            self.quota.refund(lease)
                            if self._is_quota_or_rate_limit_error(exc):
                                self.quota.cool_down(lease, exc)
                                self._advance_active_key(api_key.name)
                                next_key = self._next_key_name(api_key.name)
                                logger.warning(
                                    "Ключ %s исчерпан. Переключаюсь на ключ %s...",
                                    api_key.name,
                                    next_key or "недоступен",
                                )
                                continue

                            logger.warning(
                                "Gemini text generation failed for model=%s key=%s; trying next key/model: %s",
                                candidate_model,
                                api_key.name,
                                exc,
                            )
                            continue

                        if not response.text:
                            last_exc = RuntimeError(
                                f"Gemini model {lease.model} returned an empty response"
                            )
                            self.quota.complete(
                                lease,
                                self._response_token_count(response),
                            )
                            continue

                        finish_reason = self._finish_reason(response)
                        if finish_reason == "MAX_TOKENS":
                            last_exc = RuntimeError(
                                f"Gemini model {lease.model} truncated output at max_output_tokens={output_token_budget}"
                            )
                            self.quota.complete(
                                lease,
                                self._response_token_count(response),
                            )
                            if output_token_budget < output_token_budgets[-1]:
                                logger.info(
                                    "Gemini answer reached max_output_tokens=%s for model=%s key=%s; retrying with %s tokens",
                                    output_token_budget,
                                    lease.model,
                                    lease.key_name,
                                    output_token_budgets[-1],
                                )
                            else:
                                logger.warning(
                                    "Gemini text generation truncated for model=%s key=%s even after soft completion retry",
                                    lease.model,
                                    lease.key_name,
                                )
                            continue

                        text = response.text.strip()
                        self.quota.complete(
                            lease,
                            self._response_token_count(response)
                            or estimate_tokens(
                                prompt,
                                system_instruction,
                                text,
                                max_output_tokens=0,
                            ),
                        )
                        logger.debug(
                            "Gemini text generation used model=%s key=%s max_output_tokens=%s",
                            lease.model,
                            lease.key_name,
                            output_token_budget,
                        )
                        self._set_active_key(api_key.name)
                        return text

            if last_exc is None and local_limit_errors:
                last_exc = local_limit_errors[-1]
            raise RuntimeError(
                f"Gemini API error for model pool {candidates}: {last_exc}"
            ) from last_exc

        return await asyncio.to_thread(call_model)

    @retry(
        retry=retry_if_exception(is_retryable_gemini_unavailable),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _generate_multimodal_text(
        self,
        *,
        model: str,
        model_pool: tuple[str, ...] | None = None,
        prompt: str,
        system_instruction: str,
        attachments: list[ChatAttachment],
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> str:
        parts = self._attachment_parts(attachments)
        if not parts:
            raise RuntimeError("Cannot run multimodal generation without readable attachments")

        def call_model() -> str:
            output_token_budget = max_output_tokens or ECONOMY_MAX_OUTPUT_TOKENS
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=output_token_budget,
            )
            candidates = model_pool or (model,)
            last_exc: BaseException | None = None
            local_limit_errors: list[BaseException] = []
            estimated_tokens = estimate_tokens(
                prompt,
                system_instruction,
                max_output_tokens=output_token_budget,
            )

            for candidate_model in candidates:
                key_order = self._ordered_api_keys()
                for api_key in key_order:
                    lease: GeminiQuotaLease | None = None
                    try:
                        lease = self.quota.reserve_for_key(
                            key_name=api_key.name,
                            model=candidate_model,
                            estimated_tokens=estimated_tokens,
                        )
                    except GeminiQuotaExhausted as exc:
                        local_limit_errors.append(exc)
                        self._advance_active_key(api_key.name)
                        continue

                    try:
                        response = self.clients[api_key.name].models.generate_content(
                            model=candidate_model,
                            contents=[prompt, *parts],
                            config=config,
                        )
                    except Exception as exc:
                        last_exc = exc
                        self.quota.refund(lease)
                        if self._is_quota_or_rate_limit_error(exc):
                            self.quota.cool_down(lease, exc)
                            self._advance_active_key(api_key.name)
                            continue
                        logger.warning(
                            "Gemini multimodal generation failed for model=%s key=%s; trying next key/model: %s",
                            candidate_model,
                            api_key.name,
                            exc,
                        )
                        continue

                    if not response.text:
                        last_exc = RuntimeError(
                            f"Gemini model {lease.model} returned an empty multimodal response"
                        )
                        self.quota.complete(lease, self._response_token_count(response))
                        continue

                    text = response.text.strip()
                    self.quota.complete(
                        lease,
                        self._response_token_count(response)
                        or estimate_tokens(
                            prompt,
                            system_instruction,
                            text,
                            max_output_tokens=0,
                        ),
                    )
                    self._set_active_key(api_key.name)
                    return text

            if last_exc is None and local_limit_errors:
                last_exc = local_limit_errors[-1]
            raise RuntimeError(
                f"Gemini multimodal API error for model pool {candidates}: {last_exc}"
            ) from last_exc

        return await asyncio.to_thread(call_model)

    @staticmethod
    def _attachment_parts(attachments: list[ChatAttachment]) -> list[types.Part]:
        parts: list[types.Part] = []
        for attachment in attachments[:3]:
            data = GeminiService._attachment_bytes(attachment)
            if not data:
                continue
            parts.append(types.Part.from_bytes(data=data, mime_type=attachment.mime_type))
        return parts

    @staticmethod
    def _attachment_bytes(attachment: ChatAttachment) -> bytes:
        if attachment.base64_data:
            try:
                data = base64.b64decode(attachment.base64_data, validate=True)
            except (binascii.Error, ValueError):
                logger.warning(
                    "Skipped attachment %s because base64_data is invalid",
                    attachment.filename or "<unnamed>",
                )
                return b""
            return GeminiService._validate_attachment_size(attachment, data)

        if attachment.url:
            parsed = urlparse(attachment.url)
            if parsed.scheme not in {"http", "https"}:
                logger.warning(
                    "Skipped attachment %s because url scheme is unsupported: %s",
                    attachment.filename or "<unnamed>",
                    parsed.scheme,
                )
                return b""
            try:
                with urllib_request.urlopen(attachment.url, timeout=15) as response:
                    data = response.read(MAX_MULTIMODAL_ATTACHMENT_BYTES + 1)
            except Exception as exc:
                logger.warning(
                    "Skipped attachment %s because url download failed: %s",
                    attachment.filename or "<unnamed>",
                    exc,
                )
                return b""
            return GeminiService._validate_attachment_size(attachment, data)

        return b""

    @staticmethod
    def _validate_attachment_size(attachment: ChatAttachment, data: bytes) -> bytes:
        if not data:
            return b""
        if len(data) > MAX_MULTIMODAL_ATTACHMENT_BYTES:
            logger.warning(
                "Skipped attachment %s because it is too large: %s bytes",
                attachment.filename or "<unnamed>",
                len(data),
            )
            return b""
        return data

    def _ordered_api_keys(self) -> list:
        if not self.api_keys:
            return []

        with self._key_lock:
            start = self._active_key_index % len(self.api_keys)

        return self.api_keys[start:] + self.api_keys[:start]

    def _set_active_key(self, key_name: str) -> None:
        with self._key_lock:
            for index, api_key in enumerate(self.api_keys):
                if api_key.name == key_name:
                    self._active_key_index = index
                    return

    def _advance_active_key(self, exhausted_key_name: str) -> None:
        with self._key_lock:
            for index, api_key in enumerate(self.api_keys):
                if api_key.name == exhausted_key_name:
                    self._active_key_index = (index + 1) % len(self.api_keys)
                    return

            self._active_key_index = (self._active_key_index + 1) % len(self.api_keys)

    def _next_key_name(self, current_key_name: str) -> str:
        if not self.api_keys:
            return ""
        for index, api_key in enumerate(self.api_keys):
            if api_key.name == current_key_name:
                return self.api_keys[(index + 1) % len(self.api_keys)].name
        return self.api_keys[self._active_key_index % len(self.api_keys)].name

    @staticmethod
    def _response_token_count(response: object) -> int | None:
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is None:
            return None

        total_token_count = getattr(usage_metadata, "total_token_count", None)
        if not total_token_count:
            return None

        return int(total_token_count)

    @staticmethod
    def _finish_reason(response: object) -> str:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""

        reason = getattr(candidates[0], "finish_reason", "")
        name = getattr(reason, "name", "")
        return str(name or reason or "").upper()

    def _parse_routes(
        self,
        text: str,
        *,
        fallback_routes: list[Route] | None = None,
    ) -> list[Route]:
        fallback = list(fallback_routes or [Route.general])
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1 or end <= start:
                logger.warning("Gemini router returned non-JSON routes: %r", text)
                return fallback

            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Gemini router returned invalid JSON routes: %r", text)
                return fallback

        if not isinstance(parsed, list):
            logger.warning("Gemini router returned non-list routes: %r", text)
            return fallback

        routes: list[Route] = []
        for item in parsed:
            normalized = str(item).strip().upper()
            if normalized in Route._value2member_map_:
                route = Route(normalized)
                if route not in routes:
                    routes.append(route)

        if not routes:
            logger.warning("Gemini router returned empty routes: %r", text)
            return fallback

        if Route.general in routes and len(routes) > 1:
            routes = [route for route in routes if route != Route.general]

        return routes

    def _parse_sales_stage_transition(self, text: str) -> dict[str, object]:
        fallback = {
            "stage": "none",
            "commercial_intent": False,
            "checkout_intent": False,
        }
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                logger.warning("Sales-stage router returned non-JSON: %r", text)
                return fallback
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Sales-stage router returned invalid JSON: %r", text)
                return fallback

        if not isinstance(parsed, dict):
            logger.warning("Sales-stage router returned non-object JSON: %r", text)
            return fallback

        stage = str(parsed.get("stage") or "none").strip().lower()
        allowed_stages = {
            "none",
            "stage_2_comparison",
            "stage_3_price",
            "stage_4_checkout",
        }
        invalid_stage = stage not in allowed_stages
        if stage not in allowed_stages:
            logger.warning("Sales-stage router returned invalid stage: %r", parsed)
            stage = "none"

        commercial_intent = bool(parsed.get("commercial_intent"))
        checkout_intent = bool(parsed.get("checkout_intent"))

        if invalid_stage:
            commercial_intent = False
            checkout_intent = False
        if stage in {"stage_2_comparison", "stage_3_price", "stage_4_checkout"}:
            commercial_intent = True
        if stage != "stage_4_checkout":
            checkout_intent = False

        return {
            "stage": stage,
            "commercial_intent": commercial_intent,
            "checkout_intent": checkout_intent,
        }

    def _parse_content_followup(self, text: str) -> str:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                logger.warning("Content-followup router returned non-JSON: %r", text)
                return "none"
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("Content-followup router returned invalid JSON: %r", text)
                return "none"

        if not isinstance(parsed, dict):
            logger.warning("Content-followup router returned non-object JSON: %r", text)
            return "none"

        value = str(parsed.get("content_followup") or "none").strip().lower()
        if value not in {"none", "mechanism_detail", "safety_quality_detail"}:
            logger.warning("Content-followup router returned invalid value: %r", parsed)
            return "none"
        return value

    def _heuristic_routes(self, message: str) -> list[Route]:
        normalized = message.lower()
        exit_roleplay_keywords = (
            "выйти из роли",
            "выйди из роли",
            "выходи из роли",
            "сними маску",
            "хватит играть",
            "хватит роль",
            "завязывай",
            "давай к делу",
            "вернись к ии",
            "вернись к ai",
            "я про ии агента",
            "сколько стоит сделать такого бота",
            "сколько будет стоить сделать такого бота",
        )
        if any(keyword in normalized for keyword in exit_roleplay_keywords):
            routes = [Route.exit_roleplay]
            if re.search(r"ии|ai|агент|бот|автоматизац|стоимост|цен|сколько", normalized):
                routes.append(Route.rag_required)
            return routes

        roleplay_keywords = (
            "сыграй роль",
            "сымитир",
            "симулир",
            "продай мне",
            "покажи как",
            "будь продав",
            "будь менеджер",
            "веди диалог будто",
            "а теперь продавца",
            "теперь продавца",
        )
        if any(keyword in normalized for keyword in roleplay_keywords):
            return [Route.roleplay]

        checkout_keywords = (
            "купить",
            "заказать",
            "оформить",
            "внедрить",
            "запустить",
            "созвон",
            "демо",
            "расчет",
            "рассчитать",
            "цена",
            "стоимость",
            "сколько стоит",
            "сколько стоит бот",
            "сколько стоит агент",
            "прайс",
            "оплата",
            "беру",
            "начинаем",
        )
        rag_keywords = (
            "агент",
            "ии-агент",
            "ai agent",
            "бот",
            "чатбот",
            "база знаний",
            "knowledge base",
            "интеграция",
            "интегрировать",
            "crm",
            "срм",
            "воронка",
            "авто-корзина",
            "автокорзина",
            "заявки",
            "лиды",
            "квалификация",
            "автоматизация",
            "внедрение",
            "портфолио",
            "кейсы",
            "демо",
            "usage",
            "duration",
            "workflow",
            "automation",
            "api",
            "webhook",
            "безопас",
            "доступы",
            "данные",
            "архитектура",
            "как работает",
        )

        routes: list[Route] = []
        if any(keyword in normalized for keyword in rag_keywords):
            routes.append(Route.rag_required)
        if any(keyword in normalized for keyword in checkout_keywords):
            routes.append(Route.checkout)

        return routes or [Route.general]

    @staticmethod
    def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
        if isinstance(exc, GeminiQuotaExhausted):
            return True
        if isinstance(exc, errors.APIError):
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if status_code == 429:
                return True
        if (
            google_api_exceptions is not None
            and isinstance(exc, google_api_exceptions.ResourceExhausted)
        ):
            return True

        error_text = str(exc)
        return (
            "RESOURCE_EXHAUSTED" in error_text
            or "429" in error_text
            or "local RPM/TPM/RPD limits" in error_text
        )

    def _format_router_prompt(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        history = self._format_history(
            chat_history,
            limit=self.settings.max_history_messages,
        )
        facts = self._format_collected_facts(chat_history, client_facts)
        conversation_state = self._format_conversation_state(
            chat_history,
            message,
            client_facts,
        )
        return (
            f"Collected user facts:\n{facts}\n\n"
            f"Conversation state:\n{conversation_state}\n\n"
            f"Recent chat history:\n{history}\n\n"
            f"User message:\n{message}"
        )

    def _format_sales_stage_router_prompt(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        history = self._format_history(
            chat_history,
            limit=self.settings.max_history_messages,
        )
        facts = self._format_collected_facts(chat_history, client_facts)
        previous_assistant = self._last_assistant_message(chat_history)
        return (
            f"Collected user facts:\n{facts}\n\n"
            f"Latest assistant message:\n{previous_assistant or 'No assistant message.'}\n\n"
            f"Current user answer:\n{message}\n\n"
            f"Recent chat history:\n{history}\n\n"
            "Classify the sales-stage transition from the latest assistant message to the current user answer."
        )

    def _format_content_followup_router_prompt(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        history = self._format_history(
            chat_history,
            limit=self.settings.max_history_messages,
        )
        facts = self._format_collected_facts(chat_history, client_facts)
        previous_assistant = self._last_assistant_message(chat_history)
        return (
            f"Collected user facts:\n{facts}\n\n"
            f"Latest assistant message:\n{previous_assistant or 'No assistant message.'}\n\n"
            f"Current user answer:\n{message}\n\n"
            f"Recent chat history:\n{history}\n\n"
            "Classify the non-commercial content follow-up from the latest assistant message to the current user answer."
        )

    def _format_chat_prompt(
        self,
        message: str,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        history = self._format_history(
            chat_history,
            limit=self.settings.max_history_messages,
        )
        facts = self._format_collected_facts(chat_history, client_facts)
        conversation_state = self._format_conversation_state(
            chat_history,
            message,
            client_facts,
        )
        return (
            f"Collected user facts:\n{facts}\n\n"
            f"Conversation state:\n{conversation_state}\n\n"
            f"Chat history:\n{history}\n\n"
            f"Current user message:\n{message}"
        )

    def _format_conversation_state(
        self,
        chat_history: list[ChatHistoryMessage],
        current_message: str,
        client_facts: dict[str, object] | None = None,
    ) -> str:
        previous_assistant = self._last_assistant_message(chat_history)
        if not previous_assistant:
            return "No previous assistant question."

        lines = [f"Last assistant message: {previous_assistant}"]
        if previous_assistant.strip().endswith("?"):
            lines.append("The assistant already asked a qualifying question.")
        if self._is_vague_user_answer(current_message):
            lines.append(
                "The current user answer is vague. Do not repeat the previous question; infer intent and move forward."
            )
            goal_orientation = self._format_vague_goal_orientation(
                chat_history,
                client_facts,
            )
            if goal_orientation:
                lines.append(goal_orientation)
        return "\n".join(lines)

    def _format_vague_goal_orientation(
        self,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        facts = self.extract_client_facts(
            chat_history,
            existing_facts=client_facts,
        )
        known_parts = [
            str(facts.get("business_sphere") or "").strip(),
            str(facts.get("lead_channel") or "").strip(),
            str(facts.get("crm_or_stack") or "").strip(),
        ]
        if not any(known_parts):
            return ""

        return (
            "Suggested expert orientation for vague automation goal: "
            "propose starting with lead intake and qualification automation, then connect CRM/table and a smart cart if relevant. "
            "Do not ask the same goal question again; ask one missing scoping question or suggest a quick funnel audit."
        )

    @staticmethod
    def _fact_number(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        match = re.search(r"\d{1,3}", str(value))
        if not match:
            return None
        return int(match.group(0))

    @staticmethod
    def _is_vague_user_answer(message: str) -> bool:
        normalized = message.casefold().replace("ё", "е").strip()
        if not normalized:
            return False

        vague_markers = (
            "не знаю",
            "незнаю",
            "без разницы",
            "как скажешь",
            "на твой выбор",
            "на ваше усмотрение",
            "просто хочу",
            "сделайте как лучше",
            "как лучше",
            "не понимаю",
            "нужен бот",
            "нужен агент",
            "чем больше тем лучше",
            "сам не знаю",
            "не уверен",
            "затрудняюсь",
        )
        return any(marker in normalized for marker in vague_markers)

    def _format_collected_facts(
        self,
        chat_history: list[ChatHistoryMessage],
        client_facts: dict[str, object] | None = None,
    ) -> str:
        facts = self.extract_client_facts(
            chat_history,
            existing_facts=client_facts,
        )
        if not facts:
            return "No collected user facts."

        labels = {
            "business_sphere": "Business Sphere",
            "lead_channel": "Lead Channel",
            "crm_or_stack": "CRM/Stack",
            "website_or_social": "Website/Social",
            "automation_goal": "Automation Goal",
            "offer": "Offer",
        }
        formatted: list[str] = []
        for key, label in labels.items():
            value = facts.get(key)
            if value in (None, ""):
                continue
            formatted.append(f"{label}={value}")

        if not formatted:
            return "No collected user facts."

        return "Client Facts: " + ", ".join(formatted)

    @classmethod
    def extract_client_facts(
        cls,
        chat_history: list[ChatHistoryMessage],
        current_message: str = "",
        existing_facts: dict[str, object] | None = None,
    ) -> dict[str, object]:
        facts: dict[str, object] = {
            key: value
            for key, value in (existing_facts or {}).items()
            if value not in (None, "")
        }
        user_text = "\n".join(
            [
                *[
                    item.content
                    for item in chat_history
                    if item.role == "user"
                ],
                current_message,
            ]
        ).casefold().replace("ё", "е")
        previous_assistant = cls._last_assistant_message(chat_history).casefold().replace("ё", "е")
        current_normalized = current_message.casefold().replace("ё", "е").strip()

        if match := re.search(r"https?://\S+|(?:instagram\.com|t\.me|wa\.me)/\S+|@\w{3,}", user_text):
            facts["website_or_social"] = match.group(0).strip(".,;)")

        sphere_match = re.search(
            r"(?:сфера|ниша|бизнес|занима(?:юсь|емся))\s*[:\-]?\s*([a-zа-яё0-9\s\-]{3,60})",
            user_text,
        )
        if sphere_match:
            facts["business_sphere"] = " ".join(sphere_match.group(1).split())[:80]

        channel_patterns = (
            ("instagram", r"instagram|инстаграм|инста"),
            ("whatsapp", r"whatsapp|ватсап|вацап|waba"),
            ("telegram", r"telegram|телеграм"),
            ("website", r"сайт|лендинг|web[_ -]?site|website"),
            ("avito", r"avito|авито"),
        )
        for channel, pattern in channel_patterns:
            if re.search(pattern, user_text):
                facts["lead_channel"] = channel
                break
        if (
            "lead_channel" not in facts
            and re.fullmatch(r"(везде|со\s+всех|все\s+каналы|по\s+всем\s+каналам)", current_normalized)
            and re.search(r"где|канал|заяв|клиент|теря", previous_assistant)
        ):
            facts["lead_channel"] = "all_channels"
            facts.setdefault("automation_goal", "lead_qualification")

        stack_patterns = (
            ("amoCRM", r"\bamo\s?crm\b|\bамосрм\b|\bамо(?:crm|срм)?\b"),
            ("Bitrix24", r"bitrix|битрикс"),
            ("HubSpot", r"hubspot"),
            ("Google Sheets", r"google sheets|гугл\s+таблиц|таблиц"),
            ("Notion", r"notion"),
        )
        for stack, pattern in stack_patterns:
            if re.search(pattern, user_text):
                facts["crm_or_stack"] = stack
                break

        goal_patterns = (
            ("lead_qualification", r"квалификац|обработк[аи]\s+заяв|лид"),
            ("knowledge_base", r"база\s+знаний|knowledge\s+base|faq|частые\s+вопрос"),
            ("crm_integration", r"интеграц|crm|срм|webhook|api"),
            ("smart_cart", r"авто-?корзин|корзин|checkout|оплат"),
            ("sales_funnel", r"воронк|продаж|дожим|follow[- ]?up|фоллоу"),
        )
        for goal, pattern in goal_patterns:
            if re.search(pattern, user_text):
                facts["automation_goal"] = goal
                break

        offer_patterns = (
            ("base_ai_assistant", r"базов\w*\s+.*ассистент|ассистент"),
            ("smart_cart", r"авто-?корзин"),
            ("ai_agent_implementation", r"ии-?агент|ai\s+agent|агент\s+под\s+ключ"),
        )
        for offer, pattern in offer_patterns:
            if re.search(pattern, user_text):
                facts["offer"] = offer
                break

        return facts

    @staticmethod
    def _extract_short_numeric_answer(text: str) -> int | None:
        normalized = re.sub(r"[^\d\s,.]", " ", text)
        normalized = " ".join(normalized.replace(",", ".").split())
        if not normalized:
            return None
        match = re.fullmatch(r"(\d{1,6})(?:\.0+)?", normalized)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _is_project_budget_question(text: str) -> bool:
        if not text:
            return False
        asks_amount = re.search(r"сколько|какой\s+бюджет|какая\s+стоимость", text)
        project_context = re.search(r"бюджет|стоим|проект|внедр|агент|бот|автоматизац", text)
        return bool(asks_amount and project_context)

    @staticmethod
    def _is_target_business_question(text: str) -> bool:
        if not text:
            return False
        return bool(re.search(r"цель|задач|что\s+автоматиз|какой\s+процесс|где\s+теря", text))

    @staticmethod
    def _mentions_short_project_timeline(text: str) -> bool:
        short_timeline = r"(?:за\s+день|за\s+1\s+день|сегодня|завтра)"
        project_context = r"(?:внедр|запуст|агент|бот|интеграц|автоматизац)"
        return bool(re.search(rf"{short_timeline}.{{0,40}}{project_context}|{project_context}.{{0,40}}{short_timeline}", text))

    @staticmethod
    def _format_history(
        chat_history: list[ChatHistoryMessage],
        *,
        limit: int,
    ) -> str:
        if not chat_history:
            return "No previous messages."

        lines = [
            f"{item.role}: {item.content}"
            for item in chat_history[-limit:]
        ]
        return "\n".join(lines)

    @staticmethod
    def _ensure_followup_question_spacing(answer: str) -> str:
        normalized = (answer or "").strip()
        if not normalized or not normalized.endswith("?"):
            return normalized

        compact = re.sub(r"\n{3,}", "\n\n", normalized)
        if "\n\n" in compact:
            return compact

        match = re.search(r"(.+?)([^.?!\n][^.?!\n]*\?)\s*$", compact, flags=re.DOTALL)
        if not match:
            return compact

        main_text = match.group(1).strip()
        question = match.group(2).strip()
        if not main_text or not question:
            return compact

        return f"{main_text}\n\n{question}"
