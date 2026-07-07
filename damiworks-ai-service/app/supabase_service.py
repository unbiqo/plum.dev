from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client, create_client

from .config import Settings
from .schemas import ChatHistoryMessage, Route


logger = logging.getLogger(__name__)

# How long to keep skipping a table after a missing-table (404) error before
# checking again. Without this, a table created after process startup (e.g.
# a manual migration applied while the service is running) stays "unavailable"
# in this process's memory until it's restarted.
_AVAILABILITY_RETRY_SECONDS = 60


class _TableAvailability:
    def __init__(self) -> None:
        self._unavailable_since: float | None = None

    def blocked(self) -> bool:
        if self._unavailable_since is None:
            return False
        if time.monotonic() - self._unavailable_since >= _AVAILABILITY_RETRY_SECONDS:
            self._unavailable_since = None
            return False
        return True

    def mark_unavailable(self) -> None:
        self._unavailable_since = time.monotonic()

    def mark_available(self) -> None:
        self._unavailable_since = None


class SupabaseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self._chat_sessions_available = _TableAvailability()
        self._leads_available = _TableAvailability()
        self._quality_feedback_available = _TableAvailability()
        self._ai_conversations_available = _TableAvailability()

    async def search_knowledge_base(
        self,
        *,
        query_embedding: list[float],
        query_text: str,
        instance_id: str,
        match_threshold: float = 0.3,
        match_count: int | None = None,
    ) -> str:
        effective_match_count = min(
            match_count or self.settings.rag_match_count,
            self.settings.rag_match_count,
        )
        return await asyncio.to_thread(
            self._search_knowledge_base_sync,
            query_embedding,
            query_text,
            instance_id,
            match_threshold,
            effective_match_count,
        )

    async def get_tenant_settings(self, *, instance_id: str) -> dict[str, str]:
        return await asyncio.to_thread(self._get_tenant_settings_sync, instance_id)

    async def get_checkout_products(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._get_checkout_products_sync)

    async def get_last_message_at(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> datetime | None:
        return await asyncio.to_thread(
            self._get_last_message_at_sync,
            instance_id,
            channel,
            chat_id,
        )

    async def clear_conversation_state(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> None:
        await asyncio.to_thread(
            self._clear_conversation_state_sync,
            instance_id,
            channel,
            chat_id,
        )

    async def get_user_memory(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> str:
        return await asyncio.to_thread(
            self._get_user_memory_sync,
            instance_id,
            channel,
            chat_id,
        )

    async def get_chat_session_metadata(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._get_chat_session_metadata_sync,
            instance_id,
            channel,
            chat_id,
        )

    async def upsert_chat_session_metadata(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
        metadata: dict[str, Any],
    ) -> None:
        await asyncio.to_thread(
            self._upsert_chat_session_metadata_sync,
            instance_id,
            channel,
            chat_id,
            metadata,
        )

    async def get_lead(self, *, instance_id: str, chat_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_lead_sync, instance_id, chat_id)

    async def upsert_lead(self, lead: dict[str, Any]) -> dict[str, Any] | None:
        """Idempotent per (instance_id, chat_id). Returns the stored row or None.

        Errors are logged and swallowed — lead persistence must never break the
        user chat.
        """
        return await asyncio.to_thread(self._upsert_lead_sync, lead)

    async def create_quality_feedback(self, feedback: dict[str, Any]) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._create_quality_feedback_sync, feedback)

    async def list_quality_feedback(
        self,
        *,
        instance_id: str | None = None,
        chat_id: str | None = None,
        rating: str | None = None,
        issue_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._list_quality_feedback_sync,
            instance_id,
            chat_id,
            rating,
            issue_type,
            severity,
            status,
            created_from,
            created_to,
            limit,
        )

    async def update_quality_feedback(
        self,
        feedback_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            self._update_quality_feedback_sync,
            feedback_id,
            updates,
        )

    async def log_ai_conversation_turn(
        self,
        *,
        channel: str,
        chat_id: str,
        instance_id: str,
        user_message: str,
        assistant_answer: str,
        user_message_id: str | None = None,
        assistant_message_id: str | None = None,
        locale: str | None = None,
        source: str | None = None,
        lead_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._log_ai_conversation_turn_sync,
            channel,
            chat_id,
            instance_id,
            user_message,
            assistant_answer,
            user_message_id,
            assistant_message_id,
            locale,
            source,
            lead_status,
            metadata,
        )

    async def list_ai_conversations(
        self,
        *,
        instance_id: str | None = None,
        chat_id: str | None = None,
        has_feedback: bool | None = None,
        lead_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self._list_ai_conversations_sync,
            instance_id,
            chat_id,
            has_feedback,
            lead_status,
            date_from,
            date_to,
            limit,
            offset,
        )

    async def get_ai_conversation_detail(
        self,
        *,
        instance_id: str,
        chat_id: str,
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            self._get_ai_conversation_detail_sync,
            instance_id,
            chat_id,
        )

    async def fetch_recent_chat_history(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
        limit: int,
    ) -> list[ChatHistoryMessage]:
        return await asyncio.to_thread(
            self._fetch_recent_chat_history_sync,
            instance_id,
            channel,
            chat_id,
            limit,
        )

    async def fetch_fact_scan_history(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
        limit: int = 200,
    ) -> list[ChatHistoryMessage]:
        return await asyncio.to_thread(
            self._fetch_fact_scan_history_sync,
            instance_id,
            channel,
            chat_id,
            limit,
        )

    async def fetch_session_dialog(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
        hours: int = 6,
        limit: int = 30,
    ) -> str:
        return await asyncio.to_thread(
            self._fetch_session_dialog_sync,
            instance_id,
            channel,
            chat_id,
            hours,
            limit,
        )

    async def upsert_user_memory(
        self,
        *,
        instance_id: str,
        channel: str,
        chat_id: str,
        summary: str,
    ) -> None:
        await asyncio.to_thread(
            self._upsert_user_memory_sync,
            instance_id,
            channel,
            chat_id,
            summary,
        )

    async def log_chat(
        self,
        *,
        channel: str,
        chat_id: str,
        instance_id: str,
        message: str,
        ai_response: str,
        routes: list[Route],
        metadata: dict[str, Any] | None = None,
        user_message_id: str | None = None,
        assistant_message_id: str | None = None,
        locale: str | None = None,
        source: str | None = None,
        lead_status: str | None = None,
    ) -> None:
        await asyncio.to_thread(
            self.log_chat_sync,
            channel=channel,
            chat_id=chat_id,
            instance_id=instance_id,
            message=message,
            ai_response=ai_response,
            routes=routes,
            metadata=metadata,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            locale=locale,
            source=source,
            lead_status=lead_status,
        )

    def _search_knowledge_base_sync(
        self,
        query_embedding: list[float],
        query_text: str,
        instance_id: str,
        match_threshold: float,
        match_count: int,
    ) -> str:
        try:
            response = (
                self.client.rpc(
                    "match_knowledge_hybrid",
                    {
                        "query_embedding": query_embedding,
                        "query_text": query_text,
                        "match_threshold": match_threshold,
                        "match_count": match_count,
                        "filter_instance_id": instance_id,
                    },
                )
                .execute()
            )
        except Exception:
            logger.exception("Supabase hybrid RAG search failed")
            return ""

        rows = (response.data or [])[: self.settings.rag_match_count]
        return self._format_context(rows)

    def _get_tenant_settings_sync(self, instance_id: str) -> dict[str, str]:
        try:
            response = (
                self.client.table("tenants")
                .select(
                    ",".join(
                        [
                            "commercial_context",
                            "system_prompt_addon",
                            "router_system_prompt",
                            "hyde_system_prompt",
                            "final_system_prompt",
                            "memory_summary_system_prompt",
                        ]
                    )
                )
                .eq("instance_id", instance_id)
                .limit(1)
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch tenant settings")
            return {}

        rows = response.data or []
        if not rows:
            logger.warning("Tenant settings not found for instance_id=%s", instance_id)
            return {}

        row = rows[0]
        return {
            "commercial_context": str(row.get("commercial_context") or ""),
            "system_prompt_addon": str(row.get("system_prompt_addon") or ""),
            "router_system_prompt": str(row.get("router_system_prompt") or ""),
            "hyde_system_prompt": str(row.get("hyde_system_prompt") or ""),
            "final_system_prompt": str(row.get("final_system_prompt") or ""),
            "memory_summary_system_prompt": str(
                row.get("memory_summary_system_prompt") or ""
            ),
        }

    def _get_checkout_products_sync(self) -> list[dict[str, Any]]:
        table_name = self.settings.supabase_products_table
        allowed_ids = set(self.settings.checkout_product_ids)
        try:
            response = self.client.table(table_name).select("*").execute()
        except Exception:
            logger.exception("Failed to fetch checkout products from %s", table_name)
            return []

        rows = response.data or []
        products: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            product = self._normalize_checkout_product(row)
            if not product:
                continue
            if product["product_id"] not in allowed_ids:
                continue

            products.append(product)

        return sorted(products, key=self._checkout_product_sort_key)

    @staticmethod
    def _normalize_checkout_product(row: dict[str, Any]) -> dict[str, Any] | None:
        active = row.get("is_active", row.get("active", True))
        if active is False:
            return None

        product_id = str(
            row.get("product_id")
            or row.get("id")
            or row.get("sku")
            or row.get("slug")
            or ""
        ).strip()
        title = str(row.get("title") or row.get("name") or "").strip()
        if not product_id or not title:
            return None

        price_tenge = SupabaseService._coerce_positive_int(
            row.get("price_tenge", row.get("price"))
        )
        if price_tenge is None:
            return None

        currency = str(row.get("currency") or "KZT").strip().upper()
        if currency and currency != "KZT":
            logger.warning(
                "Skipped checkout product %s with unsupported currency=%s",
                product_id,
                currency,
            )
            return None

        dosage = str(row.get("dosage") or row.get("amount") or row.get("variant") or "").strip()
        image_url = str(row.get("image_url") or row.get("image") or "").strip()

        return {
            "product_id": product_id,
            "title": title,
            "dosage": dosage or None,
            "price_tenge": price_tenge,
            "currency": "KZT",
            "image_url": image_url or None,
        }

    @staticmethod
    def _checkout_product_sort_key(product: dict[str, Any]) -> tuple[int, str]:
        dosage = str(product.get("dosage") or product.get("product_id") or "")
        match = re.search(r"\d+", dosage)
        amount = int(match.group(0)) if match else 999
        return (amount, str(product.get("product_id") or ""))

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, float):
            return int(value) if value >= 0 else None

        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return None
        return int(digits)

    def log_chat_sync(
        self,
        *,
        channel: str,
        chat_id: str,
        instance_id: str,
        message: str,
        ai_response: str,
        routes: list[Route],
        metadata: dict[str, Any] | None = None,
        user_message_id: str | None = None,
        assistant_message_id: str | None = None,
        locale: str | None = None,
        source: str | None = None,
        lead_status: str | None = None,
    ) -> None:
        route_value = ",".join(route.value for route in routes) or Route.rag_required.value
        row = {
            "user_id": f"{channel}:{chat_id}",
            "channel": channel,
            "chat_id": chat_id,
            "instance_id": instance_id,
            "message": message,
            "ai_response": ai_response,
            "route": route_value,
        }
        if metadata:
            row["metadata"] = metadata

        try:
            self.client.table("chat_logs").insert(row).execute()
        except Exception as exc:
            if metadata and "metadata" in str(exc).casefold():
                row.pop("metadata", None)
                try:
                    self.client.table("chat_logs").insert(row).execute()
                except Exception:
                    pass
            logger.exception("Failed to write chat log to Supabase")

        self._log_ai_conversation_turn_sync(
            channel=channel,
            chat_id=chat_id,
            instance_id=instance_id,
            user_message=message,
            assistant_answer=ai_response,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            locale=locale,
            source=source,
            lead_status=lead_status,
            metadata=metadata,
        )

    def _format_context(self, rows: list[dict[str, Any]]) -> str:
        blocks: list[str] = []
        current_size = 0

        for index, row in enumerate(rows, start=1):
            content = str(row.get("content") or "").strip()
            if len(content) > self.settings.rag_chunk_max_chars:
                content = self._truncate_at_word_boundary(
                    content,
                    self.settings.rag_chunk_max_chars,
                )
            similarity = row.get("similarity")
            text_score = row.get("text_score")
            hybrid_score = row.get("hybrid_score")
            block = "\n".join(
                [
                    f"[Document {index}]",
                    f"ID: {row.get('id') or ''}",
                    f"Similarity: {similarity if similarity is not None else ''}",
                    f"Text score: {text_score if text_score is not None else ''}",
                    f"Hybrid score: {hybrid_score if hybrid_score is not None else ''}",
                    "Content:",
                    content,
                ]
            )
            next_size = current_size + len(block)
            if blocks:
                next_size += len("\n\n---\n\n")
            if next_size > self.settings.rag_context_max_chars:
                if not blocks:
                    blocks.append(
                        self._truncate_at_word_boundary(
                            block,
                            self.settings.rag_context_max_chars,
                        )
                    )
                break

            blocks.append(block)
            current_size = next_size

        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _truncate_at_word_boundary(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text.strip()

        truncated = text[:max_chars].rstrip()
        if not truncated:
            return ""

        if text[max_chars : max_chars + 1] and not text[max_chars].isspace():
            boundary = max(
                truncated.rfind(" "),
                truncated.rfind("\n"),
                truncated.rfind("\t"),
            )
            if boundary > 0:
                truncated = truncated[:boundary].rstrip()

        return truncated

    def _get_last_message_at_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> datetime | None:
        try:
            response = (
                self.client.table("chat_logs")
                .select("created_at")
                .eq("instance_id", instance_id)
                .eq("channel", channel)
                .eq("chat_id", chat_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch last chat log timestamp")
            return None

        rows = response.data or []
        if not rows:
            return None

        return self._parse_supabase_datetime(rows[0].get("created_at"))

    def _clear_conversation_state_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> None:
        filters = {
            "instance_id": instance_id,
            "channel": channel,
            "chat_id": chat_id,
        }
        for table_name in ("chat_logs", "user_memories", "chat_sessions"):
            if table_name == "chat_sessions" and self._chat_sessions_available.blocked():
                continue
            try:
                query = self.client.table(table_name).delete()
                for column, value in filters.items():
                    query = query.eq(column, value)
                query.execute()
            except Exception as exc:
                if table_name == "chat_sessions" and self._is_missing_table_error(exc):
                    self._chat_sessions_available.mark_unavailable()
                    logger.warning("chat_sessions unavailable; skipped session state clear")
                    continue
                logger.exception("Failed to clear %s for reset_context", table_name)

    def _get_user_memory_sync(self, instance_id: str, channel: str, chat_id: str) -> str:
        try:
            response = (
                self.client.table("user_memories")
                .select("summary")
                .eq("instance_id", instance_id)
                .eq("channel", channel)
                .eq("chat_id", chat_id)
                .limit(1)
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch user memory")
            return ""

        rows = response.data or []
        return str(rows[0].get("summary") or "").strip() if rows else ""

    def _get_chat_session_metadata_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
    ) -> dict[str, Any]:
        if self._chat_sessions_available.blocked():
            return {}

        try:
            response = (
                self.client.table("chat_sessions")
                .select("metadata")
                .eq("instance_id", instance_id)
                .eq("channel", channel)
                .eq("chat_id", chat_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._chat_sessions_available.mark_unavailable()
                logger.warning("chat_sessions unavailable; using chat_logs fact scan fallback")
                return {}
            self._chat_sessions_available.mark_unavailable()
            logger.exception("Failed to fetch chat session metadata")
            return {}

        self._chat_sessions_available.mark_available()
        rows = response.data or []
        if not rows:
            return {}

        metadata = rows[0].get("metadata") or {}
        return metadata if isinstance(metadata, dict) else {}

    def _upsert_chat_session_metadata_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
        metadata: dict[str, Any],
    ) -> None:
        if self._chat_sessions_available.blocked():
            return

        try:
            self.client.table("chat_sessions").upsert(
                {
                    "instance_id": instance_id,
                    "channel": channel,
                    "chat_id": chat_id,
                    "metadata": metadata,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="instance_id,channel,chat_id",
            ).execute()
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._chat_sessions_available.mark_unavailable()
                logger.warning("chat_sessions unavailable; skipped session metadata upsert")
                return
            self._chat_sessions_available.mark_unavailable()
            logger.exception("Failed to upsert chat session metadata")

    # ------------------------------------------------------------------
    # DamiWorks leads (damiworks_leads) — one row per (instance_id, chat_id)
    # ------------------------------------------------------------------

    def _get_lead_sync(self, instance_id: str, chat_id: str) -> dict[str, Any] | None:
        if self._leads_available.blocked():
            return None
        try:
            response = (
                self.client.table("damiworks_leads")
                .select("*")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._leads_available.mark_unavailable()
                logger.warning("damiworks_leads table unavailable; lead lookup skipped")
                return None
            logger.exception("Failed to fetch damiworks lead")
            return None
        self._leads_available.mark_available()
        rows = response.data or []
        return rows[0] if rows else None

    def _upsert_lead_sync(self, lead: dict[str, Any]) -> dict[str, Any] | None:
        if self._leads_available.blocked():
            return None
        payload = {k: v for k, v in lead.items() if v is not None}
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            response = (
                self.client.table("damiworks_leads")
                .upsert(payload, on_conflict="instance_id,chat_id")
                .execute()
            )
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._leads_available.mark_unavailable()
                logger.warning("damiworks_leads table unavailable; lead upsert skipped")
                return None
            logger.exception("Failed to upsert damiworks lead")
            return None
        self._leads_available.mark_available()
        rows = response.data or []
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # AI message quality feedback — instance/chat/message keyed review data
    # ------------------------------------------------------------------

    def _create_quality_feedback_sync(self, feedback: dict[str, Any]) -> dict[str, Any] | None:
        if self._quality_feedback_available.blocked():
            return None

        payload = {k: v for k, v in feedback.items() if v is not None}
        payload.setdefault("status", "open")
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            response = self.client.table("ai_message_feedback").insert(payload).execute()
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._quality_feedback_available.mark_unavailable()
                logger.warning("ai_message_feedback table unavailable; feedback insert skipped")
                return None
            logger.exception("Failed to create quality feedback")
            return None

        self._quality_feedback_available.mark_available()
        rows = response.data or []
        if rows:
            self._refresh_feedback_counts(
                str(rows[0].get("instance_id") or payload.get("instance_id") or ""),
                str(rows[0].get("chat_id") or payload.get("chat_id") or ""),
                str(rows[0].get("message_id") or payload.get("message_id") or ""),
            )
        return rows[0] if rows else None

    def _list_quality_feedback_sync(
        self,
        instance_id: str | None,
        chat_id: str | None,
        rating: str | None,
        issue_type: str | None,
        severity: str | None,
        status: str | None,
        created_from: str | None,
        created_to: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if self._quality_feedback_available.blocked():
            return []

        try:
            query = self.client.table("ai_message_feedback").select("*")
            filters = {
                "instance_id": instance_id,
                "chat_id": chat_id,
                "rating": rating,
                "issue_type": issue_type,
                "severity": severity,
                "status": status,
            }
            for column, value in filters.items():
                if value:
                    query = query.eq(column, value)
            if created_from:
                query = query.gte("created_at", created_from)
            if created_to:
                query = query.lte("created_at", created_to)
            response = (
                query.order("created_at", desc=True)
                .limit(max(1, min(limit, 500)))
                .execute()
            )
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._quality_feedback_available.mark_unavailable()
                logger.warning("ai_message_feedback table unavailable; feedback list skipped")
                return []
            logger.exception("Failed to list quality feedback")
            return []

        self._quality_feedback_available.mark_available()
        return list(response.data or [])

    def _update_quality_feedback_sync(
        self,
        feedback_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self._quality_feedback_available.blocked():
            return None

        payload = {k: v for k, v in updates.items() if v is not None}
        if not payload:
            return None
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            response = (
                self.client.table("ai_message_feedback")
                .update(payload)
                .eq("id", feedback_id)
                .execute()
            )
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._quality_feedback_available.mark_unavailable()
                logger.warning("ai_message_feedback table unavailable; feedback update skipped")
                return None
            logger.exception("Failed to update quality feedback")
            return None

        self._quality_feedback_available.mark_available()
        rows = response.data or []
        if rows:
            self._refresh_feedback_counts(
                str(rows[0].get("instance_id") or ""),
                str(rows[0].get("chat_id") or ""),
                str(rows[0].get("message_id") or ""),
            )
        return rows[0] if rows else None

    def _refresh_feedback_counts(self, instance_id: str, chat_id: str, message_id: str) -> None:
        if not instance_id or not chat_id:
            return
        conversation_count = self._count_feedback_for_conversation(instance_id, chat_id)
        try:
            self.client.table("ai_conversations").update(
                {
                    "feedback_count": conversation_count,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("instance_id", instance_id).eq("chat_id", chat_id).execute()
        except Exception:
            pass
        if not message_id:
            return
        try:
            response = (
                self.client.table("ai_message_feedback")
                .select("id")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .eq("message_id", message_id)
                .limit(1000)
                .execute()
            )
            message_count = len(response.data or [])
            self.client.table("ai_conversation_messages").update(
                {"feedback_count": message_count}
            ).eq("instance_id", instance_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
        except Exception:
            pass

    def _log_ai_conversation_turn_sync(
        self,
        channel: str,
        chat_id: str,
        instance_id: str,
        user_message: str,
        assistant_answer: str,
        user_message_id: str | None,
        assistant_message_id: str | None,
        locale: str | None,
        source: str | None,
        lead_status: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        if self._ai_conversations_available.blocked():
            return

        now = datetime.now(timezone.utc).isoformat()
        user_mid = user_message_id or f"srv_user_{uuid.uuid4()}"
        assistant_mid = assistant_message_id or f"srv_ai_{uuid.uuid4()}"
        source_value = source or channel
        metadata_value = metadata or {}

        try:
            self.client.table("ai_conversations").upsert(
                {
                    "instance_id": instance_id,
                    "chat_id": chat_id,
                    "channel": channel,
                    "locale": locale,
                    "source": source_value,
                    "status": "active",
                    "lead_status": lead_status,
                    "last_message_at": now,
                    "last_user_message": user_message,
                    "last_assistant_message": assistant_answer,
                    "metadata": metadata_value,
                    "updated_at": now,
                },
                on_conflict="instance_id,chat_id",
            ).execute()

            self.client.table("ai_conversation_messages").upsert(
                [
                    {
                        "instance_id": instance_id,
                        "chat_id": chat_id,
                        "message_id": user_mid,
                        "role": "user",
                        "content": user_message,
                        "metadata": metadata_value.get("user_message_metadata", {}),
                    },
                    {
                        "instance_id": instance_id,
                        "chat_id": chat_id,
                        "message_id": assistant_mid,
                        "role": "assistant",
                        "content": assistant_answer,
                        "metadata": metadata_value.get("assistant_message_metadata", {}),
                    },
                ],
                on_conflict="instance_id,chat_id,message_id",
            ).execute()

            message_count = self._count_conversation_messages(instance_id, chat_id)
            feedback_count = self._count_feedback_for_conversation(instance_id, chat_id)
            self.client.table("ai_conversations").update(
                {
                    "message_count": message_count,
                    "feedback_count": feedback_count,
                    "lead_status": lead_status,
                    "last_message_at": now,
                    "last_user_message": user_message,
                    "last_assistant_message": assistant_answer,
                    "updated_at": now,
                }
            ).eq("instance_id", instance_id).eq("chat_id", chat_id).execute()
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._ai_conversations_available.mark_unavailable()
                logger.warning("ai_conversations tables unavailable; conversation logging skipped")
                return
            logger.exception("Failed to log AI conversation turn")
            return

        self._ai_conversations_available.mark_available()

    def _count_conversation_messages(self, instance_id: str, chat_id: str) -> int:
        try:
            response = (
                self.client.table("ai_conversation_messages")
                .select("id")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .limit(1000)
                .execute()
            )
            return len(response.data or [])
        except Exception:
            return 0

    def _count_feedback_for_conversation(self, instance_id: str, chat_id: str) -> int:
        try:
            response = (
                self.client.table("ai_message_feedback")
                .select("id")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .limit(1000)
                .execute()
            )
            return len(response.data or [])
        except Exception:
            return 0

    def _list_ai_conversations_sync(
        self,
        instance_id: str | None,
        chat_id: str | None,
        has_feedback: bool | None,
        lead_status: str | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        if self._ai_conversations_available.blocked():
            return []

        try:
            query = self.client.table("ai_conversations").select("*")
            if instance_id:
                query = query.eq("instance_id", instance_id)
            if chat_id:
                query = query.eq("chat_id", chat_id)
            if lead_status:
                query = query.eq("lead_status", lead_status)
            if has_feedback is True:
                query = query.gt("feedback_count", 0)
            elif has_feedback is False:
                query = query.eq("feedback_count", 0)
            if date_from:
                query = query.gte("last_message_at", date_from)
            if date_to:
                query = query.lte("last_message_at", date_to)
            start = max(0, offset)
            end = start + max(1, min(limit, 500)) - 1
            response = query.order("last_message_at", desc=True).range(start, end).execute()
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._ai_conversations_available.mark_unavailable()
                logger.warning("ai_conversations table unavailable; conversation list skipped")
                return []
            logger.exception("Failed to list AI conversations")
            return []

        self._ai_conversations_available.mark_available()
        return list(response.data or [])

    def _get_ai_conversation_detail_sync(
        self,
        instance_id: str,
        chat_id: str,
    ) -> dict[str, Any] | None:
        if self._ai_conversations_available.blocked():
            return None

        try:
            conv_response = (
                self.client.table("ai_conversations")
                .select("*")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .limit(1)
                .execute()
            )
            conversation = (conv_response.data or [None])[0]
            if not conversation:
                return None

            messages_response = (
                self.client.table("ai_conversation_messages")
                .select("*")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .order("created_at", desc=False)
                .execute()
            )
            feedback_response = (
                self.client.table("ai_message_feedback")
                .select("*")
                .eq("instance_id", instance_id)
                .eq("chat_id", chat_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            if self._is_missing_table_error(exc):
                self._ai_conversations_available.mark_unavailable()
                logger.warning("ai_conversations table unavailable; conversation detail skipped")
                return None
            logger.exception("Failed to get AI conversation detail")
            return None

        feedback = list(feedback_response.data or [])
        feedback_by_message: dict[str, list[dict[str, Any]]] = {}
        for item in feedback:
            mid = str(item.get("message_id") or "")
            if mid:
                feedback_by_message.setdefault(mid, []).append(item)

        messages: list[dict[str, Any]] = []
        for message in list(messages_response.data or []):
            mid = str(message.get("message_id") or "")
            messages.append(
                {
                    **message,
                    "feedback": feedback_by_message.get(mid, []),
                    "feedback_count": len(feedback_by_message.get(mid, [])),
                }
            )

        self._ai_conversations_available.mark_available()
        return {
            "conversation": conversation,
            "messages": messages,
            "feedback": feedback,
        }

    def _fetch_recent_chat_history_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
        limit: int,
    ) -> list[ChatHistoryMessage]:
        if limit <= 0:
            return []

        try:
            response = (
                self.client.table("chat_logs")
                .select("message, ai_response, created_at")
                .eq("instance_id", instance_id)
                .eq("channel", channel)
                .eq("chat_id", chat_id)
                .order("created_at", desc=True)
                .limit(max(1, (limit + 1) // 2))
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch recent chat history")
            return []

        rows = list(reversed(response.data or []))
        history: list[ChatHistoryMessage] = []
        for row in rows:
            message = str(row.get("message") or "").strip()
            if message:
                history.append(ChatHistoryMessage(role="user", content=message))

            ai_response = str(row.get("ai_response") or "").strip()
            if ai_response:
                history.append(ChatHistoryMessage(role="assistant", content=ai_response))

        return history[-limit:]

    def _fetch_fact_scan_history_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
        limit: int,
    ) -> list[ChatHistoryMessage]:
        if limit <= 0:
            return []

        try:
            response = (
                self.client.table("chat_logs")
                .select("message, ai_response, created_at")
                .eq("instance_id", instance_id)
                .eq("channel", channel)
                .eq("chat_id", chat_id)
                .order("created_at", desc=True)
                .limit(max(1, (limit + 1) // 2))
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch fact scan history")
            return []

        rows = list(reversed(response.data or []))
        history: list[ChatHistoryMessage] = []
        for row in rows:
            message = str(row.get("message") or "").strip()
            if message:
                history.append(ChatHistoryMessage(role="user", content=message))

            ai_response = str(row.get("ai_response") or "").strip()
            if ai_response:
                history.append(ChatHistoryMessage(role="assistant", content=ai_response))

        return history[-limit:]

    def _fetch_session_dialog_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
        hours: int,
        limit: int,
    ) -> str:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        try:
            response = (
                self.client.table("chat_logs")
                .select("message, ai_response, route, created_at")
                .eq("instance_id", instance_id)
                .eq("channel", channel)
                .eq("chat_id", chat_id)
                .gte("created_at", since.isoformat())
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
        except Exception:
            logger.exception("Failed to fetch session dialog for memory")
            return ""

        rows = response.data or []
        blocks: list[str] = []
        for row in rows:
            route = row.get("route") or ""
            blocks.append(
                "\n".join(
                    [
                        f"Route: {route}",
                        f"User: {row.get('message') or ''}",
                        f"Assistant: {row.get('ai_response') or ''}",
                    ]
                )
            )

        return "\n\n".join(blocks)

    def _upsert_user_memory_sync(
        self,
        instance_id: str,
        channel: str,
        chat_id: str,
        summary: str,
    ) -> None:
        if not summary.strip():
            return

        try:
            self.client.table("user_memories").upsert(
                {
                    "instance_id": instance_id,
                    "chat_id": chat_id,
                    "channel": channel,
                    "summary": summary.strip(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="instance_id,channel,chat_id",
            ).execute()
        except Exception:
            logger.exception("Failed to upsert user memory")

    @staticmethod
    def _parse_supabase_datetime(value: Any) -> datetime | None:
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Failed to parse Supabase datetime: %r", value)
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _is_missing_table_error(exc: Exception) -> bool:
        text = str(exc)
        return (
            "PGRST205" in text
            or "Could not find the table" in text
            or "schema cache" in text and "chat_sessions" in text
        )
