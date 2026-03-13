-- Migration: Create ChatConfigs table
-- Description: Stores configuration for 5 chat models with OpenRouter integration
-- Created: 2026-02-13

-- Create ChatConfigs table
CREATE TABLE IF NOT EXISTS ChatConfigs (
  id int8 primary key generated always as identity,
  slot_number int2 not null check (slot_number between 1 and 5),
  model_name text not null,
  openrouter_model_id text not null,
  system_prompt text,
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(slot_number)
);

-- Add index for faster queries on active models
CREATE INDEX IF NOT EXISTS idx_chat_configs_active ON ChatConfigs(is_active) WHERE is_active = true;

-- Insert default configurations for 5 chat models
INSERT INTO ChatConfigs (slot_number, model_name, openrouter_model_id, system_prompt, is_active)
VALUES
  (
    1,
    'GPT-4o',
    'openai/gpt-4o',
    'Você é um assistente útil e preciso. Forneça respostas claras, objetivas e bem estruturadas. Use exemplos quando apropriado e seja sempre profissional.',
    true
  ),
  (
    2,
    'Claude 3.5 Sonnet',
    'anthropic/claude-3.5-sonnet',
    'Você é um assistente especializado em análise e raciocínio profundo. Seja detalhado em suas explicações, considere múltiplas perspectivas e forneça insights valiosos.',
    true
  ),
  (
    3,
    'Gemini Pro 1.5',
    'google/gemini-pro-1.5',
    'Você é um assistente versátil do Google. Ajude com uma ampla gama de tarefas, desde pesquisa até criação de conteúdo, sempre mantendo alta qualidade nas respostas.',
    true
  ),
  (
    4,
    'GPT-4o Mini',
    'openai/gpt-4o-mini',
    'Você é um assistente rápido e eficiente. Forneça respostas concisas mas completas, otimizando para velocidade sem sacrificar qualidade.',
    true
  ),
  (
    5,
    'Claude 3 Haiku',
    'anthropic/claude-3-haiku',
    'Você é um assistente ágil da Anthropic. Seja direto e eficiente nas respostas, mantendo precisão e utilidade em cada interação.',
    false
  )
ON CONFLICT (slot_number) DO NOTHING;

-- Add comment to table
COMMENT ON TABLE ChatConfigs IS 'Configuration for chat models used in Arcco Chat feature';
COMMENT ON COLUMN ChatConfigs.slot_number IS 'Slot position (1-5) for model configuration';
COMMENT ON COLUMN ChatConfigs.model_name IS 'User-friendly name for the model';
COMMENT ON COLUMN ChatConfigs.openrouter_model_id IS 'OpenRouter model identifier (e.g., openai/gpt-4o)';
COMMENT ON COLUMN ChatConfigs.system_prompt IS 'Default system prompt for this model';
COMMENT ON COLUMN ChatConfigs.is_active IS 'Whether this model is active and available for selection';
