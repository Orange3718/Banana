BEGIN;

CREATE TABLE IF NOT EXISTS telegram_natural_language_queries (
  id bigserial PRIMARY KEY,
  chat_id bigint,
  message_text text NOT NULL,
  intent text NOT NULL DEFAULT 'unknown',
  safe_query_key text,
  provider text NOT NULL DEFAULT 'ollama-local',
  model text NOT NULL DEFAULT 'qwen3.5:4b',
  response_text text,
  raw_model jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS telegram_nl_queries_created_idx
  ON telegram_natural_language_queries (created_at DESC);

CREATE TABLE IF NOT EXISTS telegram_safe_query_catalog (
  query_key text PRIMARY KEY,
  description text NOT NULL,
  view_name text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO telegram_safe_query_catalog(query_key, description, view_name)
VALUES
  ('status', '전체 운영 상태, 서비스, 워크플로, 승인, 로컬 추론 요약', 'v_atemoya_operational_status'),
  ('failures', '최근 n8n 실패 실행과 실패 노드', 'v_atemoya_recent_failures'),
  ('approvals', '최근 승인 요청과 대기 상태', 'v_atemoya_pending_approvals'),
  ('publications', '최근 공개 콘텐츠와 URL', 'v_atemoya_recent_publications'),
  ('local_llm', '로컬 LLM 실행 상태와 최근 결과', 'v_atemoya_local_llm_status'),
  ('sources', '최근 수집 소스와 근거 URL', 'v_atemoya_source_freshness'),
  ('incidents', '최근 시스템 인시던트', 'v_atemoya_recent_incidents'),
  ('revenue', '수익 Autopilot 작업과 채널 측정 요약', 'v_atemoya_revenue_status')
ON CONFLICT (query_key) DO UPDATE
SET description = EXCLUDED.description,
    view_name = EXCLUDED.view_name,
    enabled = true,
    updated_at = now();

CREATE OR REPLACE VIEW v_atemoya_operational_status AS
SELECT
  now() AS checked_at,
  (SELECT count(*)::int FROM workflow_entity WHERE active) AS active_workflows,
  (SELECT count(*)::int FROM workflow_entity WHERE active AND nodes::text ILIKE '%telegramTrigger%') AS active_telegram_triggers,
  (SELECT count(*)::int FROM execution_entity WHERE status = 'error' AND "startedAt" > now() - interval '24 hours') AS n8n_errors_24h,
  (SELECT count(*)::int FROM approval_requests WHERE status = 'pending') AS pending_approvals,
  (SELECT count(*)::int FROM local_llm_runs WHERE status = 'running') AS local_llm_running,
  (SELECT count(*)::int FROM local_llm_runs WHERE status = 'queued') AS local_llm_queued,
  (SELECT max(updated_at) FROM local_llm_runs WHERE status = 'complete') AS latest_local_llm_complete_at,
  (SELECT count(*)::int FROM revenue_autopilot_jobs WHERE stage IN ('queued','retry','awaiting_approval','approved','rendering','branch_ready')) AS active_revenue_jobs,
  (SELECT count(*)::int FROM content WHERE published_url IS NOT NULL AND published_at > now() - interval '7 days') AS publications_7d,
  (SELECT max(collected_at) FROM source_observations) AS latest_source_collected_at,
  (SELECT count(*)::int FROM system_incidents WHERE state = 'open') AS open_incidents;

CREATE OR REPLACE VIEW v_atemoya_recent_failures AS
SELECT
  e.id AS execution_id,
  e."workflowId" AS workflow_id,
  w.name AS workflow_name,
  e.status,
  e."startedAt" AS started_at,
  e."stoppedAt" AS stopped_at,
  left(COALESCE(ed.data::text, ''), 1200) AS error_excerpt
FROM execution_entity e
LEFT JOIN workflow_entity w ON w.id = e."workflowId"
LEFT JOIN execution_data ed ON ed."executionId" = e.id
WHERE e.status = 'error'
ORDER BY e."startedAt" DESC
LIMIT 20;

CREATE OR REPLACE VIEW v_atemoya_pending_approvals AS
SELECT
  id,
  request_type,
  title,
  status,
  risk_level,
  estimated_cost,
  requested_at,
  decided_at,
  left(COALESCE(rationale, ''), 500) AS rationale_excerpt
FROM approval_requests
ORDER BY requested_at DESC
LIMIT 20;

CREATE OR REPLACE VIEW v_atemoya_recent_publications AS
SELECT
  id,
  title,
  channel,
  status,
  published_url,
  published_at,
  source_url,
  updated_at
FROM content
WHERE published_url IS NOT NULL
ORDER BY COALESCE(published_at, updated_at) DESC
LIMIT 20;

CREATE OR REPLACE VIEW v_atemoya_local_llm_status AS
SELECT
  id,
  run_key,
  lane,
  task_name,
  provider,
  model,
  status,
  progress,
  current_step,
  started_at,
  finished_at,
  duration_ms,
  left(COALESCE(result_summary, ''), 700) AS result_summary_excerpt,
  left(COALESCE(error_summary, ''), 500) AS error_summary_excerpt,
  updated_at
FROM local_llm_runs
ORDER BY updated_at DESC
LIMIT 30;

CREATE OR REPLACE VIEW v_atemoya_source_freshness AS
SELECT
  channel,
  source_url,
  item_title,
  item_url,
  published_at,
  collected_at
FROM source_observations
ORDER BY collected_at DESC
LIMIT 30;

CREATE OR REPLACE VIEW v_atemoya_recent_incidents AS
SELECT
  id,
  component,
  check_code,
  severity,
  state,
  title,
  first_seen_at,
  last_seen_at,
  resolved_at,
  occurrence_count,
  left(COALESCE(details::text, ''), 700) AS details_excerpt
FROM system_incidents
ORDER BY last_seen_at DESC
LIMIT 20;

CREATE OR REPLACE VIEW v_atemoya_revenue_status AS
SELECT
  'autopilot_jobs'::text AS section,
  COALESCE(jsonb_object_agg(stage, count ORDER BY stage), '{}'::jsonb) AS summary,
  max(updated_at) AS latest_at
FROM (
  SELECT stage, count(*)::int AS count, max(updated_at) AS updated_at
  FROM revenue_autopilot_jobs
  GROUP BY stage
) x
UNION ALL
SELECT
  'channel_metrics'::text AS section,
  COALESCE(jsonb_object_agg(channel, jsonb_build_object('page_views', page_views, 'outbound_clicks', outbound_clicks, 'revenue', revenue_amount) ORDER BY channel), '{}'::jsonb) AS summary,
  max(metric_date)::timestamptz AS latest_at
FROM (
  SELECT
    channel,
    sum(COALESCE(page_views, 0))::int AS page_views,
    sum(COALESCE(outbound_clicks, 0))::int AS outbound_clicks,
    sum(COALESCE(revenue_amount, 0))::numeric(14,2) AS revenue_amount,
    max(metric_date) AS metric_date
  FROM revenue_channel_metrics
  WHERE metric_date >= current_date - 30
  GROUP BY channel
) y;

COMMIT;
