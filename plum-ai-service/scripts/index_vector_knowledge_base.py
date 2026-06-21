from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
warnings.filterwarnings(
    "ignore",
    message=".*google.generativeai.*",
    category=FutureWarning,
)
import google.generativeai as embedding_genai
from supabase import create_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_DIR = PROJECT_ROOT / "bp-ai-service"

DEFAULT_INSTANCE_ID = "boston_peptides_bot"
DEFAULT_SOURCE_TABLE = "rag_documents"
TARGET_TABLE = "knowledge_base"
EMBEDDING_MODEL = "text-embedding-004"
CHUNK_SIZE = 3500
CHUNK_OVERLAP = 350


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def chunk_text(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_SIZE, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start = max(0, end - CHUNK_OVERLAP)

    return chunks


def build_content(row: dict[str, Any], chunk: str, chunk_index: int, total_chunks: int) -> str:
    title = str(row.get("title") or "Untitled document").strip()
    source_url = str(row.get("source_url") or "").strip()
    return "\n".join(
        [
            f"Title: {title}",
            f"Source: {source_url}",
            f"Chunk: {chunk_index}/{total_chunks}",
            "",
            chunk,
        ]
    ).strip()


def embed_text(text: str) -> list[float]:
    try:
        model = os.getenv("GEMINI_VECTOR_EMBEDDING_MODEL", EMBEDDING_MODEL)
        model_name = model if model.startswith("models/") else f"models/{model}"
        try:
            response = embedding_genai.embed_content(
                model=model_name,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=768,
            )
        except Exception:
            if "text-embedding-004" not in model_name:
                raise
            response = embedding_genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document",
                output_dimensionality=768,
            )
    except Exception as exc:
        raise RuntimeError(f"Gemini embedding API error: {exc}") from exc

    values = response.get("embedding") if isinstance(response, dict) else None
    if not values:
        raise RuntimeError("Embedding API returned no vectors")

    values = list(values)
    if len(values) != 768:
        raise RuntimeError(f"Expected 768 embedding dimensions, got {len(values)}")

    return values


def main() -> None:
    load_dotenv(AI_SERVICE_DIR / ".env")
    load_dotenv(PROJECT_ROOT / "bp-chatbot" / ".env")

    instance_id = (
        os.getenv("INSTANCE_ID")
        or os.getenv("AI_INSTANCE_ID")
        or DEFAULT_INSTANCE_ID
    )
    source_table = os.getenv("SOURCE_RAG_TABLE", DEFAULT_SOURCE_TABLE)

    supabase = create_client(
        require_env("SUPABASE_URL"),
        require_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    embedding_genai.configure(api_key=require_env("GEMINI_API_KEY"))

    source_response = (
        supabase.table(source_table)
        .select("title, content, source_url")
        .execute()
    )
    rows = source_response.data or []
    if not rows:
        print(f"No source rows found in public.{source_table}")
        return

    print(f"Rebuilding public.{TARGET_TABLE} for instance_id={instance_id}")
    print(
        "Embedding model: "
        f"{os.getenv('GEMINI_VECTOR_EMBEDDING_MODEL', EMBEDDING_MODEL)}"
    )
    supabase.table(TARGET_TABLE).delete().eq("instance_id", instance_id).execute()

    inserted = 0
    for row_index, row in enumerate(rows, start=1):
        raw_content = str(row.get("content") or "")
        chunks = chunk_text(raw_content)
        if not chunks:
            print(f"[SKIP] row {row_index}: empty content")
            continue

        for chunk_index, chunk in enumerate(chunks, start=1):
            content = build_content(row, chunk, chunk_index, len(chunks))
            embedding = embed_text(content)
            supabase.table(TARGET_TABLE).insert(
                {
                    "instance_id": instance_id,
                    "content": content,
                    "embedding": embedding,
                }
            ).execute()
            inserted += 1
            print(
                f"[OK] row {row_index}/{len(rows)} "
                f"chunk {chunk_index}/{len(chunks)} inserted"
            )

    print(f"Done. Inserted chunks: {inserted}")


if __name__ == "__main__":
    main()
