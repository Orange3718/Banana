CREATE TABLE IF NOT EXISTS affiliate_health_checks (
  id bigserial PRIMARY KEY,
  checked_at timestamptz NOT NULL DEFAULT now(),
  asset_key text NOT NULL,
  page_url text NOT NULL,
  http_status integer,
  page_reachable boolean NOT NULL,
  disclosure_present boolean NOT NULL,
  affiliate_link_present boolean NOT NULL,
  healthy boolean NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS affiliate_health_checks_asset_checked_idx
  ON affiliate_health_checks (asset_key, checked_at DESC);

