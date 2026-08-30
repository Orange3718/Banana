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
  AND NOT (
    r.task_name = '신규 수익 콘텐츠 후보'
    AND lower(
      COALESCE(r.metadata->>'topic_title', '') || ' ' ||
      COALESCE(r.result_summary, '')
    ) ~ '(shopping|shopper|commerce|retail|payment|affiliate|creator|consumer|product|review|price|cost|tool|deal|discount|coupon|comparison|subscription|saas|beauty|travel|appliance|쇼핑|커머스|소비자|구매|가격|할인|추천|가전|여행)'
  );

COMMIT;
