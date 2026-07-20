-- Adds the cross-provider fallback chain (list of attempted "provider:model"
-- refs in walk order) to the LLM call telemetry.
alter table public.llm_call_logs
    add column if not exists fallback_chain jsonb not null default '[]'::jsonb;
