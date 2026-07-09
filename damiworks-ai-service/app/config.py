from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()

TEXT_GENERATION_MODEL = "gemini-3.1-flash-lite"
# Fallback model tried when the primary is unavailable (e.g. 503 "high demand").
# _generate_text walks the whole pool inside a single attempt, so a second model
# rescues the turn without waiting for the tenacity retry/timeout to expire.
# NOTE: gemini-2.5-flash (no "-lite") was retired by Google and must never be
# the sole fallback again — gemini-2.5-flash-lite stays as the cheap emergency
# fallback across every pool below.
TEXT_GENERATION_FALLBACK_MODEL = "gemini-2.5-flash-lite"
DEFAULT_TEXT_MODEL_POOL = (TEXT_GENERATION_MODEL, TEXT_GENERATION_FALLBACK_MODEL)

# ---------------------------------------------------------------------------
# Task-specific model profiles.
#
# Each live LLM call site passes model_profile=<name> to GeminiService.
# _generate_text (see gemini_service.py); the profile resolves to a model pool
# here. Call sites that don't pass model_profile keep using their existing
# model/model_pool fields untouched (see Settings below) — this is purely
# additive, nothing is removed.
#
# Tiers (cost roughly ascending):
#   DEFAULT_FAST_MODEL    — cheap-but-good default for most live traffic.
#   FALLBACK_CHEAP_MODEL  — emergency fallback only (provider errors/outage),
#                           not "a slightly better model" — never a profile's
#                           primary choice.
#   ESCALATION_MODEL      — stronger live model for tasks where a bad answer
#                           costs more than the extra tokens (sales/RAG
#                           grounding, medical planning/repair, extraction).
#   PREMIUM_MODEL         — reserved for rare premium/offline/eval work, never
#                           a live-chat default.
# ---------------------------------------------------------------------------
DEFAULT_FAST_MODEL = "gemini-3.1-flash-lite"
FALLBACK_CHEAP_MODEL = "gemini-2.5-flash-lite"
ESCALATION_MODEL = "gemini-3-flash-preview"
PREMIUM_MODEL = "gemini-3.5-flash"

MODEL_PROFILES: dict[str, tuple[str, ...]] = {
    "router": (DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "classifier": (DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "sales_writer": (ESCALATION_MODEL, DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "rag_writer": (ESCALATION_MODEL, DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "custom_demo_writer": (DEFAULT_FAST_MODEL, ESCALATION_MODEL, FALLBACK_CHEAP_MODEL),
    "attachment_extraction": (ESCALATION_MODEL, PREMIUM_MODEL, DEFAULT_FAST_MODEL),
    "memory_summary": (DEFAULT_FAST_MODEL, ESCALATION_MODEL, FALLBACK_CHEAP_MODEL),
    "medical_planner": (ESCALATION_MODEL, DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "medical_writer": (DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "medical_repair": (ESCALATION_MODEL, DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
    "quality_eval": (PREMIUM_MODEL, ESCALATION_MODEL),
    "default": (DEFAULT_FAST_MODEL, FALLBACK_CHEAP_MODEL),
}
# Env var name for each profile's pool override (CSV), e.g.
# MEDICAL_PLANNER_MODEL_POOL=gemini-3-flash-preview,gemini-3.1-flash-lite
_PROFILE_ENV_VARS: dict[str, str] = {
    "router": "ROUTER_MODEL_POOL",  # reuses the pre-existing env var
    "classifier": "CLASSIFIER_MODEL_POOL",
    "sales_writer": "SALES_WRITER_MODEL_POOL",
    "rag_writer": "RAG_WRITER_MODEL_POOL",
    "custom_demo_writer": "CUSTOM_DEMO_WRITER_MODEL_POOL",
    "attachment_extraction": "ATTACHMENT_EXTRACTION_MODEL_POOL",
    "memory_summary": "MEMORY_SUMMARY_MODEL_POOL",
    "medical_planner": "MEDICAL_PLANNER_MODEL_POOL",
    "medical_writer": "MEDICAL_WRITER_MODEL_POOL",
    "medical_repair": "MEDICAL_REPAIR_MODEL_POOL",
    "quality_eval": "QUALITY_EVAL_MODEL_POOL",
    "default": "DEFAULT_MODEL_POOL",
}


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
    router_model_pool: tuple[str, ...] = DEFAULT_TEXT_MODEL_POOL
    general_model_pool: tuple[str, ...] = DEFAULT_TEXT_MODEL_POOL
    rag_model_pool: tuple[str, ...] = DEFAULT_TEXT_MODEL_POOL
    embedding_model_pool: tuple[str, ...] = ("text-embedding-004", "gemini-embedding-001")
    # Task-specific pools (see MODEL_PROFILES) — populated with defaults plus
    # any per-profile env override; unknown/missing profile name at call time
    # falls back to MODEL_PROFILES["default"] (see GeminiService._generate_text).
    model_profiles: dict[str, tuple[str, ...]] = None  # type: ignore[assignment]
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


def load_model_profiles() -> dict[str, tuple[str, ...]]:
    """MODEL_PROFILES with each profile's pool overridable via its own env var.

    Missing/unset env vars keep the MODEL_PROFILES default — nothing breaks if
    none of the new *_MODEL_POOL vars are set.
    """
    return {
        profile: env_csv(env_var, list(pool))
        for profile, pool in MODEL_PROFILES.items()
        for env_var in [_PROFILE_ENV_VARS[profile]]
    }


def get_settings() -> Settings:
    router_model = TEXT_GENERATION_MODEL
    general_model = TEXT_GENERATION_MODEL
    rag_model = TEXT_GENERATION_MODEL
    embedding_model = os.getenv("GEMINI_VECTOR_EMBEDDING_MODEL", "text-embedding-004")

    router_model_pool = env_csv("ROUTER_MODEL_POOL", list(DEFAULT_TEXT_MODEL_POOL))
    general_model_pool = env_csv("GENERAL_MODEL_POOL", list(DEFAULT_TEXT_MODEL_POOL))
    rag_model_pool = env_csv("RAG_MODEL_POOL", list(DEFAULT_TEXT_MODEL_POOL))
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
        model_profiles=load_model_profiles(),
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
