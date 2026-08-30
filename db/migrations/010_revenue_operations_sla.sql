BEGIN;

CREATE TABLE IF NOT EXISTS revenue_channel_metrics (
  id bigserial PRIMARY KEY,
  content_id bigint REFERENCES content(id) ON DELETE CASCADE,
  metric_date date NOT NULL,
  channel text NOT NULL,
  page_views integer NOT NULL DEFAULT 0 CHECK (page_views >= 0),
  outbound_clicks integer NOT NULL DEFAULT 0 CHECK (outbound_clicks >= 0),
  affiliate_clicks integer NOT NULL DEFAULT 0 CHECK (affiliate_clicks >= 0),
  conversions integer NOT NULL DEFAULT 0 CHECK (conversions >= 0),
  revenue_amount numeric(14,2) NOT NULL DEFAULT 0 CHECK (revenue_amount >= 0),
  currency char(3) NOT NULL DEFAULT 'KRW',
  source text NOT NULL,
  evidence_ref text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  collected_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(content_id, metric_date, channel, source)
);

CREATE INDEX IF NOT EXISTS revenue_channel_metrics_date_idx
  ON revenue_channel_metrics(metric_date DESC, channel);

CREATE TABLE IF NOT EXISTS revenue_autopilot_reconciliations (
  id bigserial PRIMARY KEY,
  status text NOT NULL CHECK (status IN ('good','review','bad')),
  action text,
  facts jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS revenue_autopilot_reconciliations_created_idx
  ON revenue_autopilot_reconciliations(created_at DESC);

COMMIT;
