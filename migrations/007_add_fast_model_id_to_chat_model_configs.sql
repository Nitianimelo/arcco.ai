ALTER TABLE chat_model_configs
ADD COLUMN IF NOT EXISTS fast_model_id TEXT NOT NULL DEFAULT '';

ALTER TABLE chat_model_configs
ADD COLUMN IF NOT EXISTS fast_system_prompt TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN chat_model_configs.fast_model_id IS
'Optional lightweight router model that can answer simple requests directly and distill complex requests for the main chat model.';

COMMENT ON COLUMN chat_model_configs.fast_system_prompt IS
'Optional prompt for the lightweight router model. When empty, the main chat prompt is reused.';
