from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

TEXT_GENERATION_MODEL = "gemini-2.5-flash-lite"


@dataclass(frozen=True)
class GeminiApiKey:
    name: str
    value: str


@dataclass(frozen=True)
class Settings:
    gemini_api_keys: tuple[GeminiApiKey, ...]
    supabase_url: str
    supabase_service_role_key: str
    router_model: str = TEXT_GENERATION_MODEL
    general_model: str = TEXT_GENERATION_MODEL
    rag_model: str = TEXT_GENERATION_MODEL
    embedding_model: str = "text-embedding-004"
    router_model_pool: tuple[str, ...] = (TEXT_GENERATION_MODEL,)
    general_model_pool: tuple[str, ...] = (TEXT_GENERATION_MODEL,)
    rag_model_pool: tuple[str, ...] = (TEXT_GENERATION_MODEL,)
    embedding_model_pool: tuple[str, ...] = ("text-embedding-004", "gemini-embedding-001")
    supabase_rag_table: str = "rag_documents"
    max_history_messages: int = 15
    rag_match_count: int = 3
    rag_chunk_max_chars: int = 1800
    rag_context_max_chars: int = 5500
    summary_after_messages: int = 15
    use_gemini_router: bool = True
    enable_hyde_rewrite: bool = False
    enable_b2b_memory_summary: bool = True
    intelligence_shadow_enabled: bool = True
    supabase_products_table: str = "products"
    checkout_product_ids: tuple[str, ...] = (
        "ai-assistant-basic",
        "ai-smart-cart",
        "ai-agent-implementation",
    )
    # Owner lead-notification bot (repurposed damiworks_tg_bot). Optional — when
    # empty the notifier no-ops (logs only), so local/dev never breaks.
    lead_telegram_bot_token: str = ""
    lead_telegram_chat_id: str = ""
    quality_console_admin_token: str = ""

    @property
    def gemini_api_key(self) -> str:
        return self.gemini_api_keys[0].value


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return max(min_value, min(parsed, max_value))


def _dedupe(values: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def env_csv(name: str, default: list[str]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return _dedupe(default)

    return _dedupe(value.split(","))


def load_gemini_api_keys() -> tuple[GeminiApiKey, ...]:
    return (GeminiApiKey("GEMINI_API_KEY", require_env("GEMINI_API_KEY")),)


def get_settings() -> Settings:
    router_model = TEXT_GENERATION_MODEL
    general_model = TEXT_GENERATION_MODEL
    rag_model = TEXT_GENERATION_MODEL
    embedding_model = os.getenv("GEMINI_VECTOR_EMBEDDING_MODEL", "text-embedding-004")

    router_model_pool = (TEXT_GENERATION_MODEL,)
    general_model_pool = (TEXT_GENERATION_MODEL,)
    rag_model_pool = (TEXT_GENERATION_MODEL,)
    embedding_model_pool = env_csv(
        "GEMINI_VECTOR_EMBEDDING_MODEL_POOL",
        [embedding_model, "gemini-embedding-001"],
    )

    return Settings(
        gemini_api_keys=load_gemini_api_keys(),
        supabase_url=require_env("SUPABASE_URL"),
        supabase_service_role_key=require_env("SUPABASE_SERVICE_ROLE_KEY"),
        router_model=router_model,
        general_model=general_model,
        rag_model=rag_model,
        embedding_model=embedding_model,
        router_model_pool=router_model_pool,
        general_model_pool=general_model_pool,
        rag_model_pool=rag_model_pool,
        embedding_model_pool=embedding_model_pool,
        supabase_rag_table=os.getenv("SUPABASE_RAG_TABLE", "rag_documents"),
        max_history_messages=env_int(
            "MAX_HISTORY_MESSAGES",
            15,
            min_value=2,
            max_value=15,
        ),
        rag_match_count=env_int("RAG_MATCH_COUNT", 3, min_value=1, max_value=3),
        rag_chunk_max_chars=env_int(
            "RAG_CHUNK_MAX_CHARS",
            1800,
            min_value=500,
            max_value=2500,
        ),
        rag_context_max_chars=env_int(
            "RAG_CONTEXT_MAX_CHARS",
            5500,
            min_value=1500,
            max_value=7000,
        ),
        summary_after_messages=env_int(
            "SUMMARY_AFTER_MESSAGES",
            15,
            min_value=10,
            max_value=30,
        ),
        use_gemini_router=env_bool("USE_GEMINI_ROUTER", True),
        enable_hyde_rewrite=env_bool("ENABLE_HYDE_REWRITE", False),
        enable_b2b_memory_summary=env_bool("ENABLE_B2B_MEMORY_SUMMARY", True),
        intelligence_shadow_enabled=env_bool("INTELLIGENCE_SHADOW_ENABLED", True),
        supabase_products_table=os.getenv("SUPABASE_PRODUCTS_TABLE", "products"),
        checkout_product_ids=env_csv(
            "CHECKOUT_PRODUCT_IDS",
            ["ai-assistant-basic", "ai-smart-cart", "ai-agent-implementation"],
        ),
        lead_telegram_bot_token=os.getenv("LEAD_TELEGRAM_BOT_TOKEN", ""),
        lead_telegram_chat_id=os.getenv("LEAD_TELEGRAM_CHAT_ID", ""),
        quality_console_admin_token=os.getenv("QUALITY_CONSOLE_ADMIN_TOKEN", ""),
    )
