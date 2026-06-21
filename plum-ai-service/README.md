# Boston Peptides AI Service

FastAPI microservice for Gemini multi-routing, RAG lookup through Supabase, and async chat logging.

## Run locally

```powershell
cd C:\projects\bp-ai-service
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

## Endpoint

```http
POST /api/v1/chat
Content-Type: application/json
```

```json
{
  "user_id": "telegram:123456",
  "message": "Как хранить ретатрутид?",
  "chat_history": [
    {
      "role": "user",
      "content": "Привет"
    },
    {
      "role": "assistant",
      "content": "Здравствуйте."
    }
  ]
}
```

## Response

```json
{
  "route": "RAG_REQUIRED",
  "answer": "Ответ модели...",
  "checkout": null,
  "metadata": {
    "rag_context_found": true
  }
}
```

## Supabase

Apply `sql/chat_logs.sql` in Supabase SQL editor before production use.

The current RAG function is intentionally a placeholder. It tries a simple text search against the table configured by `SUPABASE_RAG_TABLE`, expecting columns:

- `title`
- `content`
- `source_url`

Replace `SupabaseService._search_knowledge_base_sync` with vector RPC or hybrid search when the RAG schema is finalized.

## Gemini quota routing

The service uses only `GEMINI_API_KEY` for every Gemini request. Additional
variables such as `GEMINI_API_KEY2` or `GEMINI_API_KEY_2` are ignored, so
traffic is not rotated away from the billing-enabled primary key.
Text generation is fixed to `gemini-2.5-flash-lite` for router, general, and RAG
answers. Text model env overrides and text model pools are intentionally ignored
to keep cost and behavior standardized:

- text model: `gemini-2.5-flash-lite`
- embedding models: `text-embedding-004`, `gemini-embedding-001`,
  `gemini-embedding-2`

Text model pools:

```env
GEMINI_ROUTER_MODEL_POOL=gemini-2.5-flash-lite
GEMINI_GENERAL_MODEL_POOL=gemini-2.5-flash-lite
GEMINI_RAG_MODEL_POOL=gemini-2.5-flash-lite
GEMINI_VECTOR_EMBEDDING_MODEL_POOL=text-embedding-004,gemini-embedding-001
```

Token budget guards:

```env
MAX_HISTORY_MESSAGES=15
RAG_MATCH_COUNT=3
RAG_CHUNK_MAX_CHARS=1800
RAG_CONTEXT_MAX_CHARS=5500
SUMMARY_AFTER_MESSAGES=15
ENABLE_B2B_MEMORY_SUMMARY=true
```

`MAX_HISTORY_MESSAGES` is clamped to 15 in code, `RAG_MATCH_COUNT` is clamped to
4, and stale sessions older than 6 hours start with empty recent history.

Embedding model settings remain separate because embeddings are not text
generation.
