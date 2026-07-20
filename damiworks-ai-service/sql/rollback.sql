-- Rollback for the 2026-07 telemetry/eval migrations. NOT applied by tooling —
-- run manually in the Supabase SQL editor only when a full rollback is needed.
-- Reverse order of application:
--   1. sql/llm_cost_dashboard.sql
--   2. sql/eval_runs.sql
--   3. sql/llm_call_logs_fallback_chain.sql
--   4. sql/llm_call_logs.sql (base table — see the warning below)

drop view if exists public.llm_cost_by_feature;
drop view if exists public.llm_cost_per_lead;

drop table if exists public.eval_runs;

alter table public.llm_call_logs
    drop column if exists fallback_chain;

-- WARNING: destructive — drops the whole LLM telemetry table with its history.
-- Uncomment only when rolling back a fresh install that has no data worth keeping.
-- drop table if exists public.llm_call_logs;
