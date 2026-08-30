BEGIN;

-- Preserve legacy rows for audit while preventing the old broad topic filter
-- from feeding generic technology news into the revenue publication queue.
UPDATE revenue_autopilot_jobs j
SET stage = 'rejected',
    last_error = 'policy-filter-v2: legacy non-revenue candidate quarantined',
    finished_at = COALESCE(j.finished_at, now()),
    updated_at = now()
FROM local_llm_runs r
WHERE r.id = j.source_run_id
  AND j.stage IN ('queued', 'retry')
  AND j.created_at < TIMESTAMPTZ '2026-08-30 07:37:00+00';

COMMIT;
