BEGIN;

-- Preserve the legacy records but remove them from the actionable surface.
-- They are generic commerce-news drafts, not reviewed Coupang product content,
-- and must not be silently treated as approved by the direct-user instruction.
UPDATE public.approval_requests
SET status='deferred',
    decided_at=COALESCE(decided_at,now()),
    decision_note=COALESCE(decision_note,'Superseded by the direct Coupang publication queue on 2026-09-14.')
WHERE request_type='revenue_content_publish' AND status='pending';

UPDATE public.approval_requests
SET status='deferred',
    decided_at=COALESCE(decided_at,now()),
    decision_note=COALESCE(decision_note,'Stale bootstrap request superseded by the verified 2026-09-14 operating state.')
WHERE status='pending'
  AND requested_at<TIMESTAMPTZ '2026-09-01 00:00:00+09'
  AND request_type IN ('external_publish','account_setup');

UPDATE public.revenue_autopilot_jobs
SET stage='rejected',
    finished_at=COALESCE(finished_at,now()),
    last_error=COALESCE(last_error,'Superseded by the direct Coupang publication queue; retained for audit.'),
    updated_at=now()
WHERE stage IN ('queued','retry','awaiting_approval','approved');

COMMIT;
