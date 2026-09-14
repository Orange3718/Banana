BEGIN;

-- The original affiliate.jobs contract stored only a digest. Direct publication
-- also needs a durable, inspectable dispatch envelope so a launchd worker can
-- resume without asking a model or a person what to publish next.
ALTER TABLE affiliate.jobs
  ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS last_error TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'affiliate_jobs_state_check'
      AND conrelid = 'affiliate.jobs'::regclass
  ) THEN
    ALTER TABLE affiliate.jobs ADD CONSTRAINT affiliate_jobs_state_check
      CHECK (state IN ('queued','running','retry_wait','succeeded','failed','manual_review','cancelled'));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'affiliate_jobs_attempt_check'
      AND conrelid = 'affiliate.jobs'::regclass
  ) THEN
    ALTER TABLE affiliate.jobs ADD CONSTRAINT affiliate_jobs_attempt_check
      CHECK (attempt >= 0 AND max_attempts > 0);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'affiliate_jobs_running_lease_check'
      AND conrelid = 'affiliate.jobs'::regclass
  ) THEN
    ALTER TABLE affiliate.jobs ADD CONSTRAINT affiliate_jobs_running_lease_check
      CHECK (state <> 'running' OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL));
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'affiliate_publications_state_check'
      AND conrelid = 'affiliate.publications'::regclass
  ) THEN
    ALTER TABLE affiliate.publications ADD CONSTRAINT affiliate_publications_state_check
      CHECK (state IN ('queued','building','deploying','published','retry_wait','manual_review','failed','cancelled'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS affiliate_jobs_dispatch_idx
  ON affiliate.jobs (kind, state, next_attempt_at, id);
CREATE INDEX IF NOT EXISTS affiliate_jobs_lease_idx
  ON affiliate.jobs (lease_expires_at) WHERE state = 'running';
CREATE INDEX IF NOT EXISTS affiliate_publications_state_idx
  ON affiliate.publications (state, verified_at, id);

CREATE OR REPLACE VIEW affiliate.v_direct_publication_status AS
SELECT
  j.id AS job_id,
  j.job_key,
  j.state AS job_state,
  p.state AS publication_state,
  j.attempt,
  j.max_attempts,
  j.next_attempt_at,
  j.payload->>'scheduled_at' AS scheduled_at,
  j.payload->>'category' AS category,
  j.payload->>'title' AS title,
  j.payload->>'public_path' AS public_path,
  p.authorization_mode,
  p.public_url,
  p.git_commit,
  p.verified_at,
  j.last_error,
  j.updated_at
FROM affiliate.jobs j
JOIN affiliate.publications p
  ON p.idempotency_key = j.payload->>'publication_key'
WHERE j.kind = 'direct_affiliate_publish';

COMMIT;
