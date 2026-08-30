CREATE TABLE IF NOT EXISTS local_llm_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  lane TEXT NOT NULL,
  task_name TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','complete','error')),
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  current_step TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  input_tokens INTEGER,
  output_tokens INTEGER,
  duration_ms INTEGER,
  result_summary TEXT,
  error_summary TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_local_llm_runs_updated ON local_llm_runs(updated_at DESC);
