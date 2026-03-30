alter table if exists public.agent_executions
  add column if not exists model_used text null,
  add column if not exists total_tokens bigint not null default 0,
  add column if not exists total_cost_usd numeric(12, 6) not null default 0;

alter table if exists public.agent_execution_agents
  add column if not exists prompt_tokens bigint not null default 0,
  add column if not exists completion_tokens bigint not null default 0,
  add column if not exists total_tokens bigint not null default 0,
  add column if not exists estimated_cost_usd numeric(12, 6) not null default 0;

update public.agent_executions
set
  total_tokens = coalesce(total_tokens, 0),
  total_cost_usd = coalesce(total_cost_usd, 0)
where total_tokens is null
   or total_cost_usd is null;

update public.agent_execution_agents
set
  prompt_tokens = coalesce(prompt_tokens, 0),
  completion_tokens = coalesce(completion_tokens, 0),
  total_tokens = coalesce(total_tokens, 0),
  estimated_cost_usd = coalesce(estimated_cost_usd, 0)
where prompt_tokens is null
   or completion_tokens is null
   or total_tokens is null
   or estimated_cost_usd is null;

create index if not exists idx_agent_executions_model_used
  on public.agent_executions (model_used);

create index if not exists idx_agent_executions_total_cost_usd
  on public.agent_executions (total_cost_usd desc);

create index if not exists idx_agent_execution_agents_total_cost_usd
  on public.agent_execution_agents (estimated_cost_usd desc);
