create extension if not exists pgcrypto;
create extension if not exists vector;
create extension if not exists pg_trgm;

create table if not exists public.tenants (
  instance_id text primary key,
  company_name text,
  commercial_context text,
  system_prompt_addon text,
  router_system_prompt text,
  hyde_system_prompt text,
  final_system_prompt text,
  memory_summary_system_prompt text,
  created_at timestamptz not null default now()
);

alter table public.tenants
  add column if not exists company_name text,
  add column if not exists commercial_context text,
  add column if not exists system_prompt_addon text,
  add column if not exists router_system_prompt text,
  add column if not exists hyde_system_prompt text,
  add column if not exists final_system_prompt text,
  add column if not exists memory_summary_system_prompt text,
  add column if not exists created_at timestamptz not null default now();

insert into public.tenants (
  instance_id,
  company_name,
  commercial_context,
  system_prompt_addon
)
values (
  'boston_peptides_bot',
  'Boston Peptides',
  'Boston Peptides strict commercial context:
- Currency: Kazakhstan tenge only. Use "тенге" or "₸". Never use rubles, dollars, or any other currency.
- Retatrutide / Ретатрутид 5 mg: 42 000 ₸.
- Retatrutide / Ретатрутид 10 mg: 49 500 ₸.
- If the client asks for a course price, calculate only from these two positions.
- If the requested course, product, quantity, discount, delivery cost, or price is not covered by this list, answer: "Сейчас я уточню актуальную стоимость этого курса в системе..." Do not invent numbers.
- For availability or price questions, answer only about the product the user asked about.
- Do not list the full catalog unless the user asks for the full catalog.
- If the user is ready to buy, collect full name, phone number, and delivery city/address or CDEK pickup point for managers.
- For a soft close, ask one short next-step question, for example whether they want to choose a dosage, reserve the item, or proceed with purchase.
- Do not invent availability, discounts, delivery promises, or medical recommendations. If the user asks what to choose medically, use RAG context and recommend consulting a qualified clinician.',
  'You are a Boston Peptides consultant-manager. Keep answers concise, practical, and sales-aware.

Default answer length: 1-3 short sentences.
ЕДИНЫЙ КОММЕРЧЕСКИЙ БЛОК: продавай результат клиента, используй только прайс Ретатрутид 5 мг - 42 000 ₸ и Ретатрутид 10 мг - 49 500 ₸, не называй другие валюты, не выдумывай цены, не вставляй CTA в каждое сообщение, не завершай фразой "Что скажете?" если она была в последних 3 репликах ассистента, разделяй технический отказ и отказ от покупки, для неясной цели похудения используй первый этап 10-12 кг, при запросе сертификатов/анализов отправляй на https://bostonpeptides.kz/ и мягко возвращай к выбору старта; в обычном Telegram checkout-card flow не собирай ФИО/телефон/адрес в чате, а если текстовый сбор контактов уже начался, не закрывай заказ без телефона и города в текущем сообщении.
Avoid long catalog blocks, repeated brand explanations, and full checkout instructions unless the user explicitly asks for them.
Do not ask a sales question in every answer. Never end two consecutive assistant messages with the same pattern, especially repeated "Хотите...".
If the user refuses a side topic, do not push that topic again. If the user refuses purchase, handle the objection professionally instead of dropping the sale.
For safety, side-effect, contraindication, or medical-risk questions, answer the concern first and do not add a purchase CTA.
Use varied, context-aware next steps only when natural: dosage choice, brief clarification, offer to compare options, or no CTA at all.
Answer in Russian unless the user clearly uses another language.'
)
on conflict (instance_id) do update
set
  company_name = excluded.company_name,
  commercial_context = excluded.commercial_context,
  system_prompt_addon = excluded.system_prompt_addon;

create table if not exists public.chat_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  channel text,
  chat_id text,
  instance_id text,
  message text not null,
  ai_response text not null,
  route text,
  created_at timestamptz not null default now()
);

alter table public.chat_logs
  add column if not exists user_id text,
  add column if not exists channel text,
  add column if not exists chat_id text,
  add column if not exists instance_id text,
  add column if not exists message text,
  add column if not exists ai_response text,
  add column if not exists route text,
  add column if not exists created_at timestamptz not null default now();

create index if not exists chat_logs_created_at_desc_idx
on public.chat_logs (created_at desc);

create index if not exists chat_logs_instance_channel_chat_created_idx
on public.chat_logs (instance_id, channel, chat_id, created_at desc);

create table if not exists public.knowledge_base (
  id bigserial primary key,
  instance_id text not null references public.tenants(instance_id) on delete cascade,
  content text not null,
  embedding vector(768) not null,
  content_tsv tsvector generated always as (
    to_tsvector('simple', coalesce(content, ''))
  ) stored,
  created_at timestamptz not null default now()
);

alter table public.knowledge_base
  add column if not exists instance_id text,
  add column if not exists content text,
  add column if not exists embedding vector(768),
  add column if not exists created_at timestamptz not null default now();

alter table public.knowledge_base
  add column if not exists content_tsv tsvector generated always as (
    to_tsvector('simple', coalesce(content, ''))
  ) stored;

create index if not exists knowledge_base_instance_id_idx
on public.knowledge_base (instance_id);

create index if not exists knowledge_base_embedding_idx
on public.knowledge_base
using hnsw (embedding vector_cosine_ops);

create index if not exists knowledge_base_content_tsv_idx
on public.knowledge_base
using gin (content_tsv);

create index if not exists knowledge_base_content_trgm_idx
on public.knowledge_base
using gin (content gin_trgm_ops);

create table if not exists public.user_memories (
  instance_id text not null default 'boston_peptides_bot',
  channel text not null,
  chat_id text not null,
  summary text,
  updated_at timestamptz not null default now(),
  primary key (instance_id, channel, chat_id)
);

alter table public.user_memories
  add column if not exists instance_id text default 'boston_peptides_bot',
  add column if not exists channel text,
  add column if not exists chat_id text,
  add column if not exists summary text,
  add column if not exists updated_at timestamptz not null default now();

update public.user_memories
set instance_id = 'boston_peptides_bot'
where instance_id is null or instance_id = '';

update public.user_memories
set channel = 'telegram'
where channel is null or channel = '';

alter table public.user_memories
  alter column instance_id set not null,
  alter column channel set not null,
  alter column chat_id set not null;

do $$
declare
  pk_name text;
  pk_columns text[];
begin
  select
    c.conname,
    array_agg(a.attname order by u.ordinality)
  into pk_name, pk_columns
  from pg_constraint c
  join unnest(c.conkey) with ordinality as u(attnum, ordinality) on true
  join pg_attribute a
    on a.attrelid = c.conrelid
   and a.attnum = u.attnum
  where c.conrelid = 'public.user_memories'::regclass
    and c.contype = 'p'
  group by c.conname;

  if pk_name is not null
     and pk_columns <> array['instance_id', 'channel', 'chat_id'] then
    execute format('alter table public.user_memories drop constraint %I', pk_name);
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.user_memories'::regclass
      and contype = 'p'
  ) then
    alter table public.user_memories
      add constraint user_memories_pkey
      primary key (instance_id, channel, chat_id);
  end if;
end $$;

create index if not exists user_memories_channel_idx
on public.user_memories (channel);

create or replace function public.match_knowledge_hybrid (
  query_embedding vector(768),
  query_text text,
  match_threshold float default 0.3,
  match_count int default 3,
  filter_instance_id text default null
)
returns table (
  id bigint,
  content text,
  similarity float,
  text_score float,
  hybrid_score float
)
language sql
stable
as $$
  with params as (
    select
      nullif(trim(coalesce(query_text, '')), '') as q,
      websearch_to_tsquery('simple', coalesce(nullif(trim(query_text), ''), '')) as tsq
  ),
  dense_candidates as (
    select kb.id
    from public.knowledge_base kb
    where kb.instance_id = filter_instance_id
      and kb.embedding is not null
      and kb.content is not null
    order by kb.embedding <=> query_embedding
    limit greatest(match_count * 20, 50)
  ),
  text_candidates as (
    select kb.id
    from public.knowledge_base kb
    cross join params p
    where kb.instance_id = filter_instance_id
      and kb.content is not null
      and p.q is not null
      and (
        kb.content_tsv @@ p.tsq
        or kb.content ilike ('%' || p.q || '%')
        or similarity(kb.content, p.q) > 0.08
      )
    order by
      case
        when kb.content_tsv @@ p.tsq
          then ts_rank_cd(kb.content_tsv, p.tsq)
        else 0
      end desc,
      similarity(kb.content, p.q) desc
    limit greatest(match_count * 20, 50)
  ),
  candidate_ids as (
    select id from dense_candidates
    union
    select id from text_candidates
  ),
  scored as (
    select
      kb.id,
      kb.content,
      greatest(0::float, 1 - (kb.embedding <=> query_embedding))::float as similarity,
      case
        when p.q is null then 0::float
        else greatest(
          case
            when kb.content_tsv @@ p.tsq
              then least(1.0, (ts_rank_cd(kb.content_tsv, p.tsq) * 8.0))::float
            else 0::float
          end,
          case
            when kb.content ilike ('%' || p.q || '%') then 0.7::float
            else 0::float
          end,
          case
            when similarity(kb.content, p.q) > 0.08
              then least(1.0, similarity(kb.content, p.q) * 2.0)::float
            else 0::float
          end
        )
      end as text_score
    from public.knowledge_base kb
    join candidate_ids c on c.id = kb.id
    cross join params p
    where kb.instance_id = filter_instance_id
      and kb.embedding is not null
      and kb.content is not null
  )
  select
    scored.id,
    scored.content,
    scored.similarity,
    scored.text_score,
    ((scored.similarity * 0.7) + (scored.text_score * 0.3))::float as hybrid_score
  from scored
  where scored.similarity >= match_threshold
     or scored.text_score > 0
  order by hybrid_score desc, similarity desc, text_score desc
  limit match_count;
$$;

create or replace function public.match_knowledge (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  filter_instance_id text
)
returns table (id bigint, content text, similarity float)
language sql
stable
as $$
  select mkh.id, mkh.content, mkh.similarity
  from public.match_knowledge_hybrid(
    query_embedding,
    '',
    match_threshold,
    match_count,
    filter_instance_id
  ) mkh;
$$;
