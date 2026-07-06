-- Instance-agnostic feedback for assistant messages.
-- Keyed around instance_id + chat_id + message_id so every current/future AI
-- employee can share the same quality workflow.

create extension if not exists pgcrypto;

create table if not exists public.ai_message_feedback (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  tenant_id text,
  client_id text,
  reviewer_id text,

  instance_id text not null,
  chat_id text not null,
  message_id text not null,

  rating text not null default 'negative'
    check (rating in ('positive', 'negative')),
  issue_type text not null default 'other',
  severity text not null default 'medium'
    check (severity in ('low', 'medium', 'high', 'critical')),
  status text not null default 'open'
    check (status in ('open', 'reviewed', 'fixed', 'ignored', 'added_to_evals')),

  user_message text,
  assistant_answer text not null,
  corrected_answer text,
  comment text,
  reviewer_note text,
  transcript_json jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,

  source text,
  environment text,
  tags text[] not null default '{}'::text[]
);

create index if not exists ai_message_feedback_instance_idx
on public.ai_message_feedback (instance_id, created_at desc);

create index if not exists ai_message_feedback_chat_idx
on public.ai_message_feedback (instance_id, chat_id, created_at desc);

create index if not exists ai_message_feedback_message_idx
on public.ai_message_feedback (instance_id, chat_id, message_id);

create index if not exists ai_message_feedback_review_idx
on public.ai_message_feedback (status, severity, issue_type, created_at desc);

create index if not exists ai_message_feedback_rating_idx
on public.ai_message_feedback (rating, created_at desc);

alter table public.ai_message_feedback
add column if not exists comment text;

alter table public.ai_message_feedback
add column if not exists reviewer_note text;

alter table public.ai_message_feedback
alter column status set default 'open';

update public.ai_message_feedback
set status = case status
  when 'new' then 'open'
  when 'triaged' then 'reviewed'
  when 'in_progress' then 'reviewed'
  when 'wont_fix' then 'ignored'
  else status
end
where status in ('new', 'triaged', 'in_progress', 'wont_fix');

alter table public.ai_message_feedback
drop constraint if exists ai_message_feedback_status_check;

alter table public.ai_message_feedback
add constraint ai_message_feedback_status_check
check (status in ('open', 'reviewed', 'fixed', 'ignored', 'added_to_evals'));
