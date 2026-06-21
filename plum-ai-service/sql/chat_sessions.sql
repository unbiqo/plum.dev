create table if not exists public.chat_sessions (
  instance_id text not null,
  channel text not null,
  chat_id text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (instance_id, channel, chat_id)
);

create index if not exists chat_sessions_updated_at_idx
on public.chat_sessions (updated_at desc);

