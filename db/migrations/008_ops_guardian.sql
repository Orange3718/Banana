BEGIN;

CREATE TABLE IF NOT EXISTS system_health_checks (
  id bigserial PRIMARY KEY,
  checked_at timestamptz NOT NULL DEFAULT now(),
  component text NOT NULL,
  check_code text NOT NULL,
  status text NOT NULL CHECK (status IN ('good', 'review', 'bad')),
  message text NOT NULL,
  latency_ms integer,
  remediated boolean NOT NULL DEFAULT false,
  remediation_action text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS system_health_checks_component_time_idx
  ON system_health_checks (component, checked_at DESC);

CREATE TABLE IF NOT EXISTS system_incidents (
  id bigserial PRIMARY KEY,
  fingerprint text NOT NULL UNIQUE,
  component text NOT NULL,
  check_code text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('review', 'bad')),
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'resolved')),
  title text NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  occurrence_count integer NOT NULL DEFAULT 1,
  last_notified_at timestamptz,
  last_remediation_at timestamptz,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS system_incidents_state_severity_idx
  ON system_incidents (state, severity, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS ops_daily_reviews (
  id bigserial PRIMARY KEY,
  review_date date NOT NULL UNIQUE,
  status text NOT NULL CHECK (status IN ('GOOD', 'REVIEW', 'BAD')),
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  summary text NOT NULL,
  provider text NOT NULL DEFAULT 'ollama-local',
  model text NOT NULL DEFAULT 'qwen3.5:4b',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  notified_at timestamptz
);

COMMIT;
