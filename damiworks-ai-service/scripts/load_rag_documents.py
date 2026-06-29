from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "bp-chatbot" / "knowledge_base" / "retatrutide"

SOURCE_URLS = {
    "biz_": "https://bostonpeptides.kz/about",
    "red_": "https://reddit.com/r/retatrutide",
    "sci_": "https://pubmed.ncbi.nlm.nih.gov/official-study-url",
}

UPPERCASE_WORDS = {"gi", "bmi", "glp", "gip", "gcg", "dna", "rna"}


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def build_title(file_path: Path) -> str:
    words = file_path.stem.split("_")
    title_words: list[str] = []

    for word in words:
        normalized = word.strip()
        if not normalized:
            continue
        if normalized.lower() in UPPERCASE_WORDS:
            title_words.append(normalized.upper())
        elif normalized.isdigit():
            title_words.append(normalized)
        else:
            title_words.append(normalized.capitalize())

    return " ".join(title_words)


def get_source_url(filename: str) -> str:
    for prefix, source_url in SOURCE_URLS.items():
        if filename.startswith(prefix):
            return source_url

    return ""


def read_text_file(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8").strip()


def load_documents() -> None:
    load_dotenv(PROJECT_ROOT / "bp-ai-service" / ".env")
    load_dotenv(PROJECT_ROOT / "bp-chatbot" / ".env")

    knowledge_dir = Path(os.getenv("KNOWLEDGE_DIR", str(DEFAULT_KNOWLEDGE_DIR)))
    if not knowledge_dir.exists():
        raise RuntimeError(f"Knowledge directory not found: {knowledge_dir}")

    supabase = create_client(
        require_env("SUPABASE_URL"),
        require_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    rag_table = os.getenv("SUPABASE_RAG_TABLE", "rag_documents")

    files = sorted(knowledge_dir.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {knowledge_dir}")
        return

    print(f"Uploading {len(files)} documents from {knowledge_dir}")
    print(f"Target table: public.{rag_table}")

    uploaded = 0
    failed = 0

    for file_path in files:
        title = build_title(file_path)
        source_url = get_source_url(file_path.name)

        try:
            content = read_text_file(file_path)
            if not content:
                print(f"[SKIP] {file_path.name}: empty file")
                continue

            response = (
                supabase.table(rag_table)
                .insert(
                    {
                        "title": title,
                        "content": content,
                        "source_url": source_url,
                    }
                )
                .execute()
            )

            row_id = response.data[0].get("id") if response.data else "unknown-id"
            uploaded += 1
            print(f"[OK] {file_path.name} -> {row_id} | {title}")

        except Exception as exc:
            failed += 1
            print(f"[ERROR] {file_path.name}: {exc}")

    print(f"Done. Uploaded: {uploaded}. Failed: {failed}.")


if __name__ == "__main__":
    load_documents()
