create extension if not exists "pgcrypto";

create table if not exists public.chat_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  channel text,
  chat_id text,
  instance_id text,
  message text not null,
  ai_response text not null,
  route text not null check (route in ('GENERAL', 'RAG_REQUIRED', 'CHECKOUT')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists chat_logs_user_id_idx
on public.chat_logs (user_id);

create index if not exists chat_logs_created_at_idx
on public.chat_logs (created_at desc);

alter table public.chat_logs
add column if not exists channel text;

alter table public.chat_logs
add column if not exists chat_id text;

alter table public.chat_logs
add column if not exists instance_id text;

create index if not exists chat_logs_instance_chat_idx
on public.chat_logs (instance_id, channel, chat_id, created_at desc);
