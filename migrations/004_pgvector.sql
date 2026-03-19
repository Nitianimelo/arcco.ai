-- =============================================================================
-- Migration 004: pgvector — Embeddings semânticos para RAG de projetos
-- =============================================================================
-- Execute no SQL Editor do Supabase Dashboard APÓS a migration 003.
-- Substitui o FTS (tsvector/GIN) por vetores densos (1536 dims, OpenAI).
-- =============================================================================

-- 1. Habilita extensão pgvector (já disponível no Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Remove coluna FTS antiga (se existir) e adiciona coluna de embedding
ALTER TABLE project_file_chunks
  DROP COLUMN IF EXISTS chunk_tsv;

ALTER TABLE project_file_chunks
  ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- 3. Remove índice GIN antigo (se existir)
DROP INDEX IF EXISTS idx_chunks_tsv;

-- 4. Cria índice HNSW para busca por similaridade coseno (rápido para 1536 dims)
-- m=16, ef_construction=64 são valores padrão balanceados
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON project_file_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 5. Função RPC para busca por similaridade semântica
-- Chamada via PostgREST: POST /rest/v1/rpc/search_project_chunks
CREATE OR REPLACE FUNCTION search_project_chunks(
  p_project_id UUID,
  p_embedding  vector(1536),
  p_top_k      INT DEFAULT 5
)
RETURNS TABLE (
  chunk_text  TEXT,
  similarity  FLOAT
)
LANGUAGE SQL
STABLE
AS $$
  SELECT
    chunk_text,
    1 - (embedding <=> p_embedding) AS similarity
  FROM project_file_chunks
  WHERE
    project_id = p_project_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> p_embedding
  LIMIT p_top_k;
$$;
