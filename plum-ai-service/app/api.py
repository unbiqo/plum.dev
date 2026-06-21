from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from .gemini_service import GeminiService
from .gemini_quota import GeminiQuotaExhausted
from .schemas import ChatHistoryMessage, ChatRequest, ChatResponse, ProductCard, Route
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
    "\n\nМогу пока быстро сориентировать, какой сценарий AI-автоматизации подойдет под вашу воронку."
)

DIALOG_STATE_KEY = "dialog_state"
VALID_SERVICE_FOCUS = {"base", "cart", "agent"}

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
PROJECT_DETAIL_PATTERN = re.compile(
    r"(?:сфера|ниша|бизнес|сайт|instagram|инст|crm|срм|воронк|заявк|лид|бот|агент|автоматизац|интеграц)",
    re.IGNORECASE,
)
AI_SERVICE_IMAGE_URLS: dict[str, str] = {}


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
        session_metadata[DIALOG_STATE_KEY] = dialog_state
        if client_facts:
            await supabase.upsert_chat_session_metadata(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
                metadata=session_metadata,
            )
        memory_context = ""

        if _is_document_request(payload.message):
            response = ChatResponse(
                route=Route.general,
                routes=[Route.general],
                answer=DOCUMENTS_SITE_ANSWER,
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

        if not is_new_session and _should_use_memory_context(payload, gemini):
            memory_context = await supabase.get_user_memory(
                instance_id=payload.instance_id,
                channel=payload.channel,
                chat_id=payload.chat_id,
            )

        routes = await gemini.classify_routes(
            payload.message,
            effective_history,
            system_prompt=tenant_settings.get("router_system_prompt", ""),
            client_facts=client_facts,
        )
        stage_transition = await gemini.classify_sales_stage_transition(
            payload.message,
            effective_history,
            client_facts=client_facts,
        )
        content_followup = await gemini.classify_content_followup(
            payload.message,
            effective_history,
            client_facts=client_facts,
        )
        sales_stage = str(stage_transition.get("stage") or "none")
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
        primary_route = _select_primary_route(routes)

        rag_context = ""
        rewritten_query = ""
        commercial_context = ""
        response_instruction = _join_non_empty(
            _format_content_followup_instruction(content_followup),
            _format_dialog_state_instruction(
                message=payload.message,
                client_facts=client_facts,
                dialog_state=dialog_state,
                sales_stage=sales_stage,
                content_followup=content_followup,
            ),
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
                _format_sales_stage_instruction(sales_stage, dialog_state),
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

        if force_checkout_from_last_price and selected_product:
            answer = _build_create_cart_answer(selected_product)
        else:
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
        contact_guard_answer = _checkout_contact_guard_answer(
            message=payload.message,
            chat_history=effective_history,
            answer=answer,
            client_facts=client_facts,
        )
        contact_guard_triggered = contact_guard_answer is not None
        if contact_guard_triggered:
            answer = contact_guard_answer or answer
            has_checkout_close_intent = False
            selected_product = None
        if _is_which_option_better_question(payload.message):
            answer = _repair_which_option_better_answer(answer, client_facts)
        if sales_stage == "stage_3_price":
            answer = _repair_stage_3_price_answer(answer, dialog_state)
        if _should_collapse_acknowledgement_after_answer(
            message=payload.message,
            chat_history=effective_history,
            routes=routes,
            sales_stage=sales_stage,
            content_followup=content_followup,
            has_explicit_commercial_intent=has_explicit_commercial_intent,
        ):
            answer = _build_acknowledgement_continuation_answer(
                client_facts=client_facts,
                dialog_state=dialog_state,
            )
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
                    answer=_build_generation_error_answer(exc),
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
                answer=_build_generation_fallback_answer(payload),
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
                answer=_build_generation_error_answer(exc),
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
            answer=_build_generation_fallback_answer(payload),
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
            "Gemini сейчас не ответил: Google вернул лимит/квоту по API-ключу. "
            "Проверьте billing/quota для проекта этого GEMINI_API_KEY."
        )
    return "Gemini сейчас не ответил. Подробная причина записана в логах микросервиса."


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
            "Напишите нишу и где приходят заявки — сайт, Instagram, WhatsApp или Telegram."
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
        "Напишите, где сейчас теряются заявки — с этого начнем расчет."
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
            "где сейчас теряются заявки",
        )
    )


def _is_document_request(message: str) -> bool:
    normalized = message.casefold().replace("ё", "е")
    return any(re.search(pattern, normalized) for pattern in DOCUMENT_REQUEST_PATTERNS)


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


def _format_sales_stage_instruction(stage: str, dialog_state: dict[str, object] | None = None) -> str:
    state = dialog_state or {}
    focus = str(state.get("last_offer_product") or state.get("current_product_focus") or "").strip()
    focus_instruction = ""
    if focus in VALID_SERVICE_FOCUS:
        focus_instruction = (
            f" Current local service focus is {focus}. "
            "If the user is agreeing to the latest estimate or implementation offer, keep this service focus unless the user explicitly asks to compare or change it."
        )
    if stage == "stage_2_comparison":
        return (
            "Sales stage: STAGE 2 - consultation and comparison.\n"
            "The user has agreed to learn the options. Compare relevant AI service options: Базовый ИИ-ассистент, Авто-корзина под ключ, or ИИ-агент под ключ. "
            "Compare them by business value for the client's funnel and recommend the next practical step. "
            "Give a reasoned recommendation for this client after the comparison. Do not name exact prices yet. "
            "Do not create or mention a cart/card/checkout. Do not repeat the previous permission question. End by offering to calculate the project."
            f"{focus_instruction}"
        )
    if stage == "stage_3_price":
        return (
            "Sales stage: STAGE 3 - price presentation.\n"
            "The user has agreed after the comparison or after a concrete project estimate offer. "
            "If there is a current local service focus, present the estimate for that focused service first and do not switch the recommendation. "
            "If there is no focus, present the exact prices or ranges from dynamic product context. "
            "Do not ask a long questionnaire in this stage. Do not create or mention a cart/card/checkout yet. End by asking whether to proceed with the focused or recommended project."
            f"{focus_instruction}"
        )
    if stage == "stage_4_checkout":
        return (
            "Sales stage: STAGE 4 - checkout.\n"
            "The user has agreed after seeing the project estimate/package. Keep the text short and let the backend product card/buttons handle checkout or handoff."
            f"{focus_instruction}"
        )
    return ""


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
    automation_goal = str(client_facts.get("automation_goal") or "").strip()

    last_offer_type = str(dialog_state.get("last_offer_type") or "")
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
            if re.search(r"базов\w*\s+ассистент|ассистент", normalized) and re.search(r"\d", normalized):
                state["price_base_presented"] = True
            if re.search(r"авто-?корзин|корзин", normalized) and re.search(r"\d", normalized):
                state["price_cart_presented"] = True
            if re.search(r"ии-?агент|агент|интеграц|crm|срм", normalized) and re.search(r"\d", normalized):
                state["price_agent_presented"] = True

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
        }:
            normalized[key] = bool(value)
            continue
        if key == "asked_offers":
            if isinstance(value, list):
                normalized[key] = [str(item)[:80] for item in value if str(item).strip()][-12:]
            continue
        if key in {"last_offer_type", "last_offer_basis"}:
            text = str(value).strip()
            if text:
                normalized[key] = text[:80]
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
    automation_goal = str(client_facts.get("automation_goal") or "").strip()
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
    if re.search(r"базов\w*\s+ассистент|ассистент", normalized_answer) and re.search(r"\d", normalized_answer):
        state["price_base_presented"] = True
    if re.search(r"авто-?корзин|корзин", normalized_answer) and re.search(r"\d", normalized_answer):
        state["price_cart_presented"] = True
    if re.search(r"ии-?агент|агент|интеграц|crm|срм", normalized_answer) and re.search(r"\d", normalized_answer):
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

    phone_match = PHONE_PATTERN.search(normalized)
    if not phone_match:
        return False

    digits = re.sub(r"\D", "", phone_match.group(0))
    if len(digits) < 7:
        return False

    return bool(PROJECT_DETAIL_PATTERN.search(normalized))


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
