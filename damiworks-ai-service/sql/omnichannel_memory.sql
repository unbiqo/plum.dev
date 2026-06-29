alter table public.chat_logs
add column if not exists channel text,
add column if not exists chat_id text,
add column if not exists instance_id text;

create index if not exists chat_logs_channel_chat_id_created_at_idx
on public.chat_logs (channel, chat_id, created_at desc);

create index if not exists chat_logs_instance_id_created_at_idx
on public.chat_logs (instance_id, created_at desc);

create table if not exists public.user_memories (
  chat_id text primary key,
  channel text,
  summary text,
  updated_at timestamptz not null default now()
);

create index if not exists user_memories_channel_idx
on public.user_memories (channel);
