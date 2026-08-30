CREATE TABLE IF NOT EXISTS source_observations (
  id BIGSERIAL PRIMARY KEY,
  channel TEXT NOT NULL,
  source_url TEXT NOT NULL,
  item_title TEXT,
  item_url TEXT,
  engagement JSONB NOT NULL DEFAULT '{}'::jsonb,
  published_at TIMESTAMPTZ,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(channel,item_url)
);
CREATE INDEX IF NOT EXISTS idx_source_observations_collected ON source_observations(collected_at DESC);
