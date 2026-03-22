create table if not exists public.agent_model_overrides (
  agent_id text primary key,
  model text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.set_agent_model_override_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_set_agent_model_override_updated_at on public.agent_model_overrides;
create trigger trg_set_agent_model_override_updated_at
before update on public.agent_model_overrides
for each row
execute function public.set_agent_model_override_updated_at();

alter table public.agent_model_overrides enable row level security;

drop policy if exists "authenticated_read_agent_model_overrides" on public.agent_model_overrides;
create policy "authenticated_read_agent_model_overrides"
on public.agent_model_overrides
for select
to authenticated
using (true);

create index if not exists idx_agent_model_overrides_updated_at
  on public.agent_model_overrides (updated_at desc);
