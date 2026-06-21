create extension if not exists "pgcrypto";
create extension if not exists "pg_trgm";

create table if not exists public.chat_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  message text not null,
  ai_response text not null,
  route text,
  created_at timestamptz not null default now()
);

create index if not exists chat_logs_created_at_desc_idx
on public.chat_logs (created_at desc);

create table if not exists public.rag_documents (
  id uuid primary key default gen_random_uuid(),
  title text,
  content text,
  source_url text,
  created_at timestamptz not null default now()
);

create index if not exists rag_documents_content_trgm_idx
on public.rag_documents
using gin (content gin_trgm_ops);

create index if not exists rag_documents_title_trgm_idx
on public.rag_documents
using gin (title gin_trgm_ops);

create index if not exists rag_documents_created_at_desc_idx
on public.rag_documents (created_at desc);
