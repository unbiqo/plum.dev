-- DamiWorks website consultant leads.
-- One row per (instance_id, chat_id); the conversation flow upserts it on intake
-- completion and updates the same row when contact is collected.

create table if not exists public.damiworks_leads (
  id uuid primary key default gen_random_uuid(),
  instance_id text not null,
  chat_id text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  status text not null default 'intake_completed'
    check (status in ('intake_completed', 'contact_requested', 'contact_collected', 'notified', 'closed')),
  source text not null default 'damiworks_site',
  locale text,

  package_recommended text,
  package_selected text,
  business_type text,
  channels text[] not null default '{}',
  tasks text[] not null default '{}',
  handoff_target text,
  volume text,
  timeline text,
  estimated_setup_price text,
  estimated_monthly_price text,

  user_contact_name text,
  user_contact_phone text,
  user_contact_telegram text,
  contact_raw text,

  summary text,
  transcript_json jsonb not null default '[]'::jsonb,
  interest_level text,

  notified_at timestamptz,
  contact_collected_at timestamptz,
  closed_at timestamptz,

  unique (instance_id, chat_id)
);

create index if not exists damiworks_leads_status_idx on public.damiworks_leads (status);
create index if not exists damiworks_leads_created_at_idx on public.damiworks_leads (created_at desc);
