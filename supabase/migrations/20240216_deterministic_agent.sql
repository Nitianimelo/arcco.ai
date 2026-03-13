-- Architecture: Deterministic Agent
-- Tables for tracking intents, tasks, and context

-- 1. Intent Actions Map
CREATE TABLE IF NOT EXISTS intent_actions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  intent_key TEXT UNIQUE NOT NULL,
  description TEXT,
  action_type TEXT NOT NULL, -- "deterministic" | "reasoning" | "hybrid"
  function_endpoint TEXT,
  required_params JSONB DEFAULT '[]',
  optional_params JSONB DEFAULT '[]',
  prompt_template TEXT,
  max_tokens INTEGER DEFAULT 500,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed Initial Intents
INSERT INTO intent_actions (intent_key, description, action_type, function_endpoint, required_params) 
VALUES
('web_search', 'Busca na web via Tavily', 'deterministic', 'web_search', '["query"]'),
('generate_file', 'Gera arquivos (PDF, Excel, PPTX, DOCX)', 'deterministic', 'generate_file', '["type", "content", "title"]'),
('ocr_scan', 'Lê texto de imagens', 'deterministic', 'ocr_scan', '["image_url"]'),
('deep_search', 'Pesquisa profunda com múltiplos passos', 'hybrid', 'deep_search', '["topic"]'),
('general_chat', 'Chat geral', 'reasoning', 'llm_call', '["message"]')
ON CONFLICT (intent_key) DO NOTHING;

-- 2. Task Runs (Execution Logs)
CREATE TABLE IF NOT EXISTS task_runs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  intent_key TEXT NOT NULL,
  status TEXT DEFAULT 'pending', -- pending | running | completed | failed
  plan JSONB,
  steps JSONB DEFAULT '[]',
  final_result TEXT,
  tokens_used INTEGER DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_task_runs_conversation ON task_runs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status);

-- 3. Conversation Context (Compressed Memory)
CREATE TABLE IF NOT EXISTS conversation_context (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id TEXT UNIQUE NOT NULL,
  user_id TEXT NOT NULL,
  summary TEXT,
  key_facts JSONB DEFAULT '[]',
  last_intent TEXT,
  turn_count INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Usage Metrics
CREATE TABLE IF NOT EXISTS usage_metrics (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  intent_key TEXT NOT NULL,
  action_type TEXT NOT NULL,
  tokens_input INTEGER DEFAULT 0,
  tokens_output INTEGER DEFAULT 0,
  execution_time_ms INTEGER,
  was_keyword_matched BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Grant permissions (Adjust based on your RLS requirements)
ALTER TABLE intent_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY;

-- Simple policies (Adjust for production!)
CREATE POLICY "Public read intents" ON intent_actions FOR SELECT USING (true);
CREATE POLICY "Users can insert runs" ON task_runs FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can select own runs" ON task_runs FOR SELECT USING (true); -- simplified for demo
CREATE POLICY "Users can manage context" ON conversation_context FOR ALL USING (true);
CREATE POLICY "Users can insert metrics" ON usage_metrics FOR INSERT WITH CHECK (true);
