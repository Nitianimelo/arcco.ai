-- Migration: Consolidate chat model settings into a single table
-- Source of truth after this migration: chat_model_configs

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS chat_model_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_number INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  openrouter_model_id TEXT NOT NULL,
  system_prompt TEXT DEFAULT '',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chat_model_configs_slot_number_check CHECK (slot_number > 0),
  CONSTRAINT chat_model_configs_slot_number_key UNIQUE (slot_number)
);

CREATE INDEX IF NOT EXISTS idx_chat_model_configs_active
  ON chat_model_configs (is_active)
  WHERE is_active = TRUE;

INSERT INTO chat_model_configs (
  slot_number,
  model_name,
  openrouter_model_id,
  system_prompt,
  is_active
)
SELECT
  c.slot_number,
  c.model_name,
  c.openrouter_model_id,
  COALESCE(c.system_prompt, ''),
  COALESCE(c.is_active, TRUE)
FROM "ChatConfigs" c
WHERE NOT EXISTS (
  SELECT 1 FROM chat_model_configs existing
);

COMMENT ON TABLE chat_model_configs IS 'Single source of truth for chat model configs used by admin and normal chat.';
COMMENT ON COLUMN chat_model_configs.slot_number IS 'Display order of the model in the chat selector.';
COMMENT ON COLUMN chat_model_configs.model_name IS 'User-facing model name.';
COMMENT ON COLUMN chat_model_configs.openrouter_model_id IS 'OpenRouter model identifier.';
COMMENT ON COLUMN chat_model_configs.system_prompt IS 'Default system prompt for this chat model.';
COMMENT ON COLUMN chat_model_configs.is_active IS 'Whether the model is available in the UI.';
