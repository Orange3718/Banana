BEGIN;

CREATE TABLE IF NOT EXISTS revenue_autopilot_jobs (
  id bigserial PRIMARY KEY,
  job_key text NOT NULL UNIQUE,
  source_run_id bigint UNIQUE REFERENCES local_llm_runs(id) ON DELETE SET NULL,
  content_id bigint REFERENCES content(id) ON DELETE SET NULL,
  approval_request_id bigint REFERENCES approval_requests(id) ON DELETE SET NULL,
  stage text NOT NULL DEFAULT 'queued' CHECK (stage IN (
    'queued','running','retry','awaiting_approval','approved','rendering',
    'branch_ready','published','rejected','failed'
  )),
  priority integer NOT NULL DEFAULT 0,
  attempt integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 3,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  artifact_path text,
  result_url text,
  last_error text,
  qa jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS revenue_autopilot_stage_next_idx
  ON revenue_autopilot_jobs (stage, next_attempt_at, priority DESC, id);

CREATE UNIQUE INDEX IF NOT EXISTS revenue_autopilot_one_review_idx
  ON revenue_autopilot_jobs ((stage)) WHERE stage = 'awaiting_approval';

COMMIT;
