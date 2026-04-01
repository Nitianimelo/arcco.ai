create extension if not exists pgcrypto;

create table if not exists public.chat_model_configs (
  id uuid primary key default gen_random_uuid(),
  slot_number integer not null,
  model_name text not null,
  openrouter_model_id text not null,
  fast_model_id text not null default '',
  fast_system_prompt text not null default '',
  system_prompt text not null default '',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_chat_model_configs_slot
  on public.chat_model_configs (slot_number asc);

create index if not exists idx_chat_model_configs_active_slot
  on public.chat_model_configs (is_active, slot_number asc);

create or replace function public.set_chat_model_configs_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_set_chat_model_configs_updated_at on public.chat_model_configs;
create trigger trg_set_chat_model_configs_updated_at
before update on public.chat_model_configs
for each row
execute function public.set_chat_model_configs_updated_at();

alter table public.chat_model_configs enable row level security;

drop policy if exists "authenticated_read_chat_model_configs" on public.chat_model_configs;
create policy "authenticated_read_chat_model_configs"
on public.chat_model_configs
for select
to authenticated
using (true);

comment on table public.chat_model_configs is 'Slots configuráveis do Chat Normal exibidos no admin e no seletor do chat.';
comment on column public.chat_model_configs.slot_number is 'Posição visual do slot no dropdown do Chat Normal.';
comment on column public.chat_model_configs.model_name is 'Nome exibido ao usuário.';
comment on column public.chat_model_configs.openrouter_model_id is 'ID real do modelo no OpenRouter.';
comment on column public.chat_model_configs.fast_model_id is 'Modelo leve opcional usado para responder pedidos simples e destilar briefs para o modelo principal.';
comment on column public.chat_model_configs.fast_system_prompt is 'Prompt opcional do modelo leve; se vazio, o sistema reutiliza o prompt do modelo principal.';
comment on column public.chat_model_configs.system_prompt is 'Prompt default aplicado ao usar este slot no Chat Normal.';
