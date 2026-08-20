BEGIN;

-- Speeds up safe, single-item claiming by the execution orchestrator.
CREATE INDEX IF NOT EXISTS business_unit_tasks_auto_ready_idx
  ON business_unit_tasks (priority, due_date, id)
  WHERE status = 'ready'
    AND automation_mode = 'AUTO'
    AND owner_required = false;

COMMENT ON INDEX business_unit_tasks_auto_ready_idx IS
  'Queue index for approval-free Atemoya execution orchestrators.';

COMMIT;
