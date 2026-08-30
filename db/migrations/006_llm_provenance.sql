ALTER TABLE local_llm_runs ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'ollama-local';
ALTER TABLE local_llm_runs ADD COLUMN IF NOT EXISTS inference_note TEXT;
CREATE INDEX IF NOT EXISTS idx_local_llm_runs_provider ON local_llm_runs(provider);
