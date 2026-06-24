from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client, create_client

from .config import Settings
from .schemas import ChatHistoryMessage, Route


logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self._chat_sessions_available: bool | None = None

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
                    return
                except Exception:
                    pass
            logger.exception("Failed to write chat log to Supabase")

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
            if table_name == "chat_sessions" and self._chat_sessions_available is False:
                continue
            try:
                query = self.client.table(table_name).delete()
                for column, value in filters.items():
                    query = query.eq(column, value)
                query.execute()
            except Exception as exc:
                if table_name == "chat_sessions" and self._is_missing_table_error(exc):
                    self._chat_sessions_available = False
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
        if self._chat_sessions_available is False:
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
                self._chat_sessions_available = False
                logger.warning("chat_sessions unavailable; using chat_logs fact scan fallback")
                return {}
            self._chat_sessions_available = False
            logger.exception("Failed to fetch chat session metadata")
            return {}

        self._chat_sessions_available = True
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
        if self._chat_sessions_available is False:
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
                self._chat_sessions_available = False
                logger.warning("chat_sessions unavailable; skipped session metadata upsert")
                return
            self._chat_sessions_available = False
            logger.exception("Failed to upsert chat session metadata")

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
