BEGIN;

CREATE TABLE IF NOT EXISTS business_ideas (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  external_key text UNIQUE,
  title text NOT NULL,
  summary text,
  source_url text,
  source_name text,
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new','evaluating','approved','rejected','archived')),
  score numeric(6,2),
  evaluation jsonb NOT NULL DEFAULT '{}'::jsonb,
  discovered_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiments (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  business_idea_id bigint REFERENCES business_ideas(id) ON DELETE SET NULL,
  name text NOT NULL,
  hypothesis text,
  status text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','running','paused','completed','cancelled')),
  started_at timestamptz,
  ended_at timestamptz,
  success_metric text,
  target_value numeric,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assets (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  experiment_id bigint REFERENCES experiments(id) ON DELETE SET NULL,
  slug text UNIQUE,
  name text NOT NULL,
  asset_type text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  canonical_url text,
  repository_path text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_id bigint REFERENCES assets(id) ON DELETE SET NULL,
  external_key text UNIQUE,
  title text NOT NULL,
  channel text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  source_url text,
  published_url text,
  body_ref text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revenue (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_id bigint REFERENCES assets(id) ON DELETE SET NULL,
  occurred_on date NOT NULL,
  amount numeric(14,2) NOT NULL CHECK (amount >= 0),
  currency char(3) NOT NULL DEFAULT 'KRW',
  source text NOT NULL,
  status text NOT NULL DEFAULT 'reported' CHECK (status IN ('estimated','reported','settled','reversed')),
  evidence_ref text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cost (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_id bigint REFERENCES assets(id) ON DELETE SET NULL,
  occurred_on date NOT NULL,
  amount numeric(14,2) NOT NULL CHECK (amount >= 0),
  currency char(3) NOT NULL DEFAULT 'KRW',
  category text NOT NULL,
  vendor text,
  evidence_ref text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS executions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  workflow_key text NOT NULL,
  n8n_execution_id text,
  correlation_id text,
  status text NOT NULL CHECK (status IN ('running','success','failed','retrying','cancelled')),
  attempt integer NOT NULL DEFAULT 1 CHECK (attempt > 0),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  error_summary text,
  input_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_summary jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS agent_actions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  execution_id bigint REFERENCES executions(id) ON DELETE SET NULL,
  agent_name text NOT NULL,
  action_type text NOT NULL,
  status text NOT NULL,
  requires_approval boolean NOT NULL DEFAULT false,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  agent_action_id bigint REFERENCES agent_actions(id) ON DELETE SET NULL,
  approval_key text UNIQUE,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired','cancelled')),
  requested_via text NOT NULL DEFAULT 'telegram',
  requested_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz,
  decided_by text,
  decision_note text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS business_ideas_status_score_idx ON business_ideas (status, score DESC);
CREATE INDEX IF NOT EXISTS experiments_status_idx ON experiments (status);
CREATE INDEX IF NOT EXISTS content_asset_status_idx ON content (asset_id, status);
CREATE INDEX IF NOT EXISTS revenue_asset_date_idx ON revenue (asset_id, occurred_on DESC);
CREATE INDEX IF NOT EXISTS cost_asset_date_idx ON cost (asset_id, occurred_on DESC);
CREATE INDEX IF NOT EXISTS executions_workflow_started_idx ON executions (workflow_key, started_at DESC);
CREATE INDEX IF NOT EXISTS approvals_status_requested_idx ON approvals (status, requested_at);

COMMIT;
