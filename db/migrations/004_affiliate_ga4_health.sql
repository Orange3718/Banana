ALTER TABLE affiliate_health_checks
  ADD COLUMN IF NOT EXISTS ga4_config_valid boolean;

