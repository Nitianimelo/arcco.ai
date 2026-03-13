-- Migration: Create ApiKeys table
-- Description: Stores API keys for external services (OpenRouter, etc.)
-- Created: 2026-02-14

CREATE TABLE IF NOT EXISTS ApiKeys (
  id int8 primary key generated always as identity,
  provider text not null,
  api_key text not null,
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(provider)
);

-- Add comment to table
COMMENT ON TABLE ApiKeys IS 'Stores API keys for external services';
