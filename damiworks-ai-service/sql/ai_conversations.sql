-- Conversation-first quality review storage.
-- These tables are instance-agnostic and can hold DamiWorks demos, client demos,
-- and future production AI employee chats under their own instance_id.

create extension if not exists pgcrypto;

create table if not exists public.ai_conversations (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_message_at timestamptz not null default now(),

  tenant_id text,
  client_id text,

  instance_id text not null,
  chat_id text not null,
  channel text,
  locale text,
  source text,
  status text not null default 'active',
  lead_status text,
  message_count integer not null default 0,
  feedback_count integer not null default 0,
  last_user_message text,
  last_assistant_message text,
  metadata jsonb not null default '{}'::jsonb,

  constraint ai_conversations_instance_chat_unique unique (instance_id, chat_id)
);

create table if not exists public.ai_conversation_messages (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),

  instance_id text not null,
  chat_id text not null,
  message_id text not null,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  turn_index integer,
  metadata jsonb not null default '{}'::jsonb,
  feedback_count integer not null default 0,

  constraint ai_conversation_messages_unique unique (instance_id, chat_id, message_id)
);

create index if not exists ai_conversations_instance_last_idx
on public.ai_conversations (instance_id, last_message_at desc);

create index if not exists ai_conversations_last_idx
on public.ai_conversations (last_message_at desc);

create index if not exists ai_conversations_feedback_idx
on public.ai_conversations (feedback_count, last_message_at desc);

create index if not exists ai_conversation_messages_chat_idx
on public.ai_conversation_messages (instance_id, chat_id, created_at);

create index if not exists ai_conversation_messages_message_idx
on public.ai_conversation_messages (instance_id, chat_id, message_id);

-- Best-effort legacy backfill for older DamiWorks consultant logs.
-- This only uses content already stored in chat_logs; it does not invent
-- transcripts for chats that were never logged server-side.
insert into public.ai_conversations (
  instance_id,
  chat_id,
  channel,
  source,
  last_message_at,
  last_user_message,
  last_assistant_message,
  message_count,
  metadata
)
select
  coalesce(nullif(cl.instance_id, ''), 'damiworks_site') as instance_id,
  cl.chat_id,
  max(cl.channel) as channel,
  'legacy_chat_logs' as source,
  max(cl.created_at) as last_message_at,
  (array_agg(cl.message order by cl.created_at desc))[1] as last_user_message,
  (array_agg(cl.ai_response order by cl.created_at desc))[1] as last_assistant_message,
  count(*)::int * 2 as message_count,
  jsonb_build_object('backfilled_from', 'chat_logs') as metadata
from public.chat_logs cl
where cl.chat_id is not null
group by coalesce(nullif(cl.instance_id, ''), 'damiworks_site'), cl.chat_id
on conflict (instance_id, chat_id) do nothing;

insert into public.ai_conversation_messages (
  instance_id,
  chat_id,
  message_id,
  role,
  content,
  turn_index,
  created_at,
  metadata
)
select
  instance_id,
  chat_id,
  message_id,
  role,
  content,
  turn_index,
  created_at,
  jsonb_build_object('backfilled_from', 'chat_logs')
from (
  select
    coalesce(nullif(cl.instance_id, ''), 'damiworks_site') as instance_id,
    cl.chat_id,
    'legacy_' || cl.id::text || '_user' as message_id,
    'user' as role,
    cl.message as content,
    (row_number() over (partition by coalesce(nullif(cl.instance_id, ''), 'damiworks_site'), cl.chat_id order by cl.created_at) * 2 - 1)::int as turn_index,
    cl.created_at
  from public.chat_logs cl
  where cl.chat_id is not null
  union all
  select
    coalesce(nullif(cl.instance_id, ''), 'damiworks_site') as instance_id,
    cl.chat_id,
    'legacy_' || cl.id::text || '_assistant' as message_id,
    'assistant' as role,
    cl.ai_response as content,
    (row_number() over (partition by coalesce(nullif(cl.instance_id, ''), 'damiworks_site'), cl.chat_id order by cl.created_at) * 2)::int as turn_index,
    cl.created_at + interval '1 millisecond' as created_at
  from public.chat_logs cl
  where cl.chat_id is not null
) legacy_messages
on conflict (instance_id, chat_id, message_id) do nothing;

-- Best-effort legacy lead transcript backfill. Only array-shaped transcripts
-- with role/content entries are imported. State dictionaries stored by some
-- vertical demos are intentionally skipped because they are not message logs.
insert into public.ai_conversations (
  instance_id,
  chat_id,
  source,
  status,
  lead_status,
  last_message_at,
  message_count,
  metadata
)
select
  dl.instance_id,
  dl.chat_id,
  'legacy_damiworks_leads' as source,
  coalesce(dl.status, 'active') as status,
  dl.status as lead_status,
  coalesce(dl.updated_at, dl.created_at, now()) as last_message_at,
  jsonb_array_length(dl.transcript_json)::int as message_count,
  jsonb_build_object('backfilled_from', 'damiworks_leads')
from public.damiworks_leads dl
where dl.instance_id is not null
  and dl.chat_id is not null
  and jsonb_typeof(dl.transcript_json) = 'array'
on conflict (instance_id, chat_id) do nothing;

insert into public.ai_conversation_messages (
  instance_id,
  chat_id,
  message_id,
  role,
  content,
  turn_index,
  created_at,
  metadata
)
select
  dl.instance_id,
  dl.chat_id,
  'legacy_lead_' || dl.id::text || '_' || item.ordinality::text as message_id,
  case
    when item.value->>'role' in ('user', 'assistant', 'system') then item.value->>'role'
    else 'system'
  end as role,
  coalesce(item.value->>'content', item.value->>'text', '') as content,
  item.ordinality::int as turn_index,
  coalesce(dl.created_at, now()) + ((item.ordinality::int - 1) * interval '1 millisecond') as created_at,
  jsonb_build_object('backfilled_from', 'damiworks_leads')
from public.damiworks_leads dl
cross join lateral jsonb_array_elements(dl.transcript_json) with ordinality as item(value, ordinality)
where dl.instance_id is not null
  and dl.chat_id is not null
  and jsonb_typeof(dl.transcript_json) = 'array'
  and coalesce(item.value->>'content', item.value->>'text', '') <> ''
on conflict (instance_id, chat_id, message_id) do nothing;
