-- Cost-per-lead dashboard views over llm_call_logs.
-- Apply after sql/llm_call_logs.sql (and sql/llm_call_logs_fallback_chain.sql).

-- Full cost of processing one lead (all features, per day).
create or replace view llm_cost_per_lead as
select
    instance_id,
    conversation_id,
    date(created_at) as day,
    count(*) as llm_calls,
    count(distinct task_type) as features_used,
    sum(input_tokens) as input_tokens,
    sum(output_tokens) as output_tokens,
    sum(total_cost_usd) as total_cost_usd,
    max(latency_ms) as slowest_call_ms,
    sum(case when fallback_used then 1 else 0 end) as fallback_calls
from llm_call_logs
group by instance_id, conversation_id, date(created_at);

-- Spend and latency broken down by feature/provider/model.
create or replace view llm_cost_by_feature as
select
    instance_id,
    task_type,
    provider,
    selected_model,
    count(*) as calls,
    sum(input_tokens) as input_tokens,
    sum(output_tokens) as output_tokens,
    sum(total_cost_usd) as total_cost_usd,
    avg(latency_ms) as avg_latency_ms,
    sum(case when fallback_used then 1 else 0 end) as fallback_calls
from llm_call_logs
group by instance_id, task_type, provider, selected_model;
