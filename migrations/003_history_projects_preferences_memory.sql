-- =============================================================================
-- Migration 003: Histórico, Projetos, Preferências e Memória do Usuário
-- =============================================================================
-- Execute no SQL Editor do Supabase Dashboard.
-- RLS: desabilitado (backend usa service role key, igual ao padrão do projeto).
-- Ordem importa: projects antes de conversations (FK).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. PROJETOS
-- Cada usuário pode ter múltiplos projetos com instruções personalizadas.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      TEXT NOT NULL,
  name         TEXT NOT NULL,
  instructions TEXT NOT NULL DEFAULT '',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);

-- -----------------------------------------------------------------------------
-- 2. CONVERSAÇÕES
-- Cada conversa pertence a um usuário e opcionalmente a um projeto.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    TEXT NOT NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  title      TEXT NOT NULL DEFAULT 'Nova Conversa',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);

-- -----------------------------------------------------------------------------
-- 3. MENSAGENS
-- Cada mensagem pertence a uma conversa. Cascade on delete.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content         TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at      ON messages(created_at);

-- -----------------------------------------------------------------------------
-- 4. ARQUIVOS DOS PROJETOS (knowledge base persistente)
-- Arquivos ficam no bucket project-files no Supabase Storage.
-- O texto extraído é armazenado em extracted_text para o chunking FTS.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_files (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id        TEXT NOT NULL,
  file_name      TEXT NOT NULL,
  storage_path   TEXT NOT NULL,
  extracted_text TEXT,
  mime_type      TEXT NOT NULL DEFAULT 'application/octet-stream',
  size_bytes     BIGINT NOT NULL DEFAULT 0,
  status         TEXT NOT NULL DEFAULT 'processing'
                 CHECK (status IN ('processing', 'ready', 'failed')),
  error_message  TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_status     ON project_files(project_id, status);

-- -----------------------------------------------------------------------------
-- 4b. CHUNKS FTS — Full Text Search nativo do PostgreSQL
-- Cada arquivo é dividido em chunks com tsvector para busca em português.
-- Índice GIN garante performance mesmo com milhares de chunks.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_file_chunks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_file_id UUID NOT NULL REFERENCES project_files(id) ON DELETE CASCADE,
  project_id      UUID NOT NULL REFERENCES projects(id)      ON DELETE CASCADE,
  chunk_text      TEXT NOT NULL,
  chunk_tsv       tsvector GENERATED ALWAYS AS
                  (to_tsvector('portuguese', chunk_text)) STORED,
  chunk_index     INTEGER NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_project_id ON project_file_chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv        ON project_file_chunks USING GIN(chunk_tsv);

-- -----------------------------------------------------------------------------
-- 5. PREFERÊNCIAS DO USUÁRIO
-- Uma linha por usuário. Upsert on conflict(user_id).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id             TEXT PRIMARY KEY,
  theme               TEXT NOT NULL DEFAULT 'dark',
  display_name        TEXT,
  custom_instructions TEXT,
  logo_url            TEXT,
  occupation          TEXT,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 6. MEMÓRIA DO USUÁRIO
-- Uma linha por usuário. Texto síntese acumulativo, máx 1500 chars.
-- Upsert on conflict(user_id).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_memory (
  user_id    TEXT PRIMARY KEY,
  content    TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- BUCKET: Criar manualmente no Supabase Dashboard → Storage
--   Nome: project-files
--   Acesso: Private (acesso apenas via service role key no backend)
-- =============================================================================
