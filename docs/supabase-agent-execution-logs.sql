create extension if not exists pgcrypto;
create extension if not exists pg_cron;

create table if not exists public.agent_executions (
  id uuid primary key default gen_random_uuid(),
  conversation_id text null,
  session_id text null,
  project_id text null,
  user_id text null,
  request_text text not null,
  request_source text null,
  supervisor_agent text null default 'chat',
  model_used text null,
  status text not null default 'running',
  final_error text null,
  total_tokens bigint not null default 0,
  total_cost_usd numeric(12, 6) not null default 0,
  started_at timestamptz not null default now(),
  finished_at timestamptz null,
  duration_ms integer null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_executions_created_at
  on public.agent_executions (created_at desc);

create index if not exists idx_agent_executions_status
  on public.agent_executions (status);

create index if not exists idx_agent_executions_conversation_id
  on public.agent_executions (conversation_id);

create index if not exists idx_agent_executions_session_id
  on public.agent_executions (session_id);

create index if not exists idx_agent_executions_user_id
  on public.agent_executions (user_id);

create index if not exists idx_agent_executions_model_used
  on public.agent_executions (model_used);

create index if not exists idx_agent_executions_total_cost_usd
  on public.agent_executions (total_cost_usd desc);

create table if not exists public.agent_execution_agents (
  id uuid primary key default gen_random_uuid(),
  execution_id uuid not null references public.agent_executions(id) on delete cascade,
  agent_key text not null,
  agent_name text not null,
  model text null,
  role text null,
  route text null,
  sequence_no integer not null default 0,
  status text not null default 'running',
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  error_text text null,
  prompt_tokens bigint not null default 0,
  completion_tokens bigint not null default 0,
  total_tokens bigint not null default 0,
  estimated_cost_usd numeric(12, 6) not null default 0,
  started_at timestamptz not null default now(),
  finished_at timestamptz null,
  duration_ms integer null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_execution_agents_execution_id
  on public.agent_execution_agents (execution_id);

create index if not exists idx_agent_execution_agents_execution_sequence
  on public.agent_execution_agents (execution_id, sequence_no);

create index if not exists idx_agent_execution_agents_agent_key
  on public.agent_execution_agents (agent_key);

create index if not exists idx_agent_execution_agents_status
  on public.agent_execution_agents (status);

create index if not exists idx_agent_execution_agents_total_cost_usd
  on public.agent_execution_agents (estimated_cost_usd desc);

create table if not exists public.agent_execution_logs (
  id bigserial primary key,
  execution_id uuid not null references public.agent_executions(id) on delete cascade,
  execution_agent_id uuid null references public.agent_execution_agents(id) on delete cascade,
  sequence_no bigint not null default 0,
  level text not null default 'info',
  event_type text not null,
  message text null,
  tool_name text null,
  tool_args jsonb null,
  tool_result jsonb null,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_execution_logs_execution_id
  on public.agent_execution_logs (execution_id, id);

create index if not exists idx_agent_execution_logs_execution_agent_id
  on public.agent_execution_logs (execution_agent_id, id);

create index if not exists idx_agent_execution_logs_event_type
  on public.agent_execution_logs (event_type);

create index if not exists idx_agent_execution_logs_created_at
  on public.agent_execution_logs (created_at desc);

create or replace function public.set_agent_execution_duration()
returns trigger
language plpgsql
as $$
begin
  if new.finished_at is not null and new.started_at is not null then
    new.duration_ms := floor(extract(epoch from (new.finished_at - new.started_at)) * 1000);
  end if;
  return new;
end;
$$;

drop trigger if exists trg_set_agent_execution_duration on public.agent_executions;
create trigger trg_set_agent_execution_duration
before insert or update on public.agent_executions
for each row
execute function public.set_agent_execution_duration();

drop trigger if exists trg_set_agent_execution_agent_duration on public.agent_execution_agents;
create trigger trg_set_agent_execution_agent_duration
before insert or update on public.agent_execution_agents
for each row
execute function public.set_agent_execution_duration();

create or replace view public.v_agent_execution_summary as
select
  e.id,
  e.conversation_id,
  e.session_id,
  e.project_id,
  e.user_id,
  e.request_text,
  e.request_source,
  e.supervisor_agent,
  e.status,
  e.final_error,
  e.started_at,
  e.finished_at,
  e.duration_ms,
  e.created_at,
  coalesce(a.agent_count, 0) as agent_count,
  coalesce(a.failed_agent_count, 0) as failed_agent_count,
  coalesce(l.log_count, 0) as log_count
from public.agent_executions e
left join (
  select
    execution_id,
    count(*) as agent_count,
    count(*) filter (where status = 'failed') as failed_agent_count
  from public.agent_execution_agents
  group by execution_id
) a on a.execution_id = e.id
left join (
  select
    execution_id,
    count(*) as log_count
  from public.agent_execution_logs
  group by execution_id
) l on l.execution_id = e.id;

create or replace function public.cleanup_agent_logs()
returns void
language plpgsql
as $$
begin
  delete from public.agent_executions
  where created_at < now() - interval '1 hour';
end;
$$;

do $outer$
begin
  if not exists (
    select 1
    from cron.job
    where jobname = 'cleanup_agent_logs_hourly'
  ) then
    perform cron.schedule(
      'cleanup_agent_logs_hourly',
      '0 * * * *',
      'select public.cleanup_agent_logs();'
    );
  end if;
end
$outer$;

alter table public.agent_executions replica identity full;
alter table public.agent_execution_agents replica identity full;
alter table public.agent_execution_logs replica identity full;

do $outer$
begin
  begin
    alter publication supabase_realtime add table public.agent_executions;
  exception when duplicate_object then
    null;
  end;

  begin
    alter publication supabase_realtime add table public.agent_execution_agents;
  exception when duplicate_object then
    null;
  end;

  begin
    alter publication supabase_realtime add table public.agent_execution_logs;
  exception when duplicate_object then
    null;
  end;
end
$outer$;

alter table public.agent_executions enable row level security;
alter table public.agent_execution_agents enable row level security;
alter table public.agent_execution_logs enable row level security;

drop policy if exists "authenticated_read_agent_executions" on public.agent_executions;
create policy "authenticated_read_agent_executions"
on public.agent_executions
for select
to authenticated
using (true);

drop policy if exists "authenticated_read_agent_execution_agents" on public.agent_execution_agents;
create policy "authenticated_read_agent_execution_agents"
on public.agent_execution_agents
for select
to authenticated
using (true);

drop policy if exists "authenticated_read_agent_execution_logs" on public.agent_execution_logs;
create policy "authenticated_read_agent_execution_logs"
on public.agent_execution_logs
for select
to authenticated
using (true);
