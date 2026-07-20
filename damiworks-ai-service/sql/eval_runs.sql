-- Nightly quality-eval results. One row per judged conversation sample.
-- Written by scripts/nightly_quality_eval.py via SupabaseService.insert_eval_run.
create table if not exists eval_runs (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    run_date date not null,
    conversation_id text,
    instance_id text not null,
    chat_id text,
    scores jsonb not null,
    verdict text not null check (verdict in ('pass', 'warn', 'fail')),
    recommendations text,
    judge_model text,
    batch_id text,
    total_cost_usd numeric(12, 8)
);

create index if not exists eval_runs_run_date_idx on eval_runs (run_date);
create index if not exists eval_runs_instance_idx on eval_runs (instance_id);
create index if not exists eval_runs_verdict_idx on eval_runs (verdict);
