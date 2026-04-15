-- Migration 008: adiciona coluna metadata JSONB à tabela messages
-- Armazena designs, text_doc e files gerados numa conversa para restauração posterior.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS metadata JSONB NULL;

COMMENT ON COLUMN messages.metadata IS
  'Artefatos gerados pelo assistente: { designs?: string[], text_doc?: {title,content}, files?: [{filename,url,type}] }';
