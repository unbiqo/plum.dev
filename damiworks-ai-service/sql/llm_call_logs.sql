create table if not exists public.llm_call_logs (
    id uuid primary key,
    conversation_id text not null,
    message_id text null,
    tenant_id text null,
    instance_id text not null,
    provider text not null default 'gemini',
    model_profile text null,
    selected_model text null,
    task_type text null,
    input_tokens integer not null default 0,
    output_tokens integer not null default 0,
    total_tokens integer not null default 0,
    cached_input_tokens integer null,
    thinking_tokens integer null,
    estimated boolean not null default false,
    input_cost_usd numeric null,
    output_cost_usd numeric null,
    total_cost_usd numeric null,
    pricing_missing boolean not null default false,
    latency_ms integer not null default 0,
    success boolean not null default true,
    error_type text null,
    fallback_used boolean not null default false,
    fallback_reason text null,
    escalation_used boolean not null default false,
    escalation_reason text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_llm_call_logs_conversation_id
    on public.llm_call_logs (conversation_id);

create index if not exists idx_llm_call_logs_instance_id
    on public.llm_call_logs (instance_id);

create index if not exists idx_llm_call_logs_tenant_id
    on public.llm_call_logs (tenant_id);

create index if not exists idx_llm_call_logs_selected_model
    on public.llm_call_logs (selected_model);

create index if not exists idx_llm_call_logs_model_profile
    on public.llm_call_logs (model_profile);

create index if not exists idx_llm_call_logs_created_at
    on public.llm_call_logs (created_at desc);
