-- Affiliate Business OS core. Additive and isolated from public revenue tables.
CREATE SCHEMA IF NOT EXISTS affiliate;

CREATE TABLE IF NOT EXISTS affiliate.program_accounts (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  environment TEXT NOT NULL CHECK (environment IN ('test','prod')),
  provider TEXT NOT NULL,
  account_ref TEXT NOT NULL,
  market TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'inactive' CHECK (state IN ('inactive','ready','suspended')),
  credential_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (environment, provider, account_ref)
);

CREATE TABLE IF NOT EXISTS affiliate.policy_versions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id),
  version INT NOT NULL CHECK (version > 0),
  source_ref TEXT NOT NULL,
  verified_at TIMESTAMPTZ NOT NULL,
  capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
  contract JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (account_id, version)
);

CREATE TABLE IF NOT EXISTS affiliate.experiment_extensions (
  experiment_id BIGINT PRIMARY KEY REFERENCES public.experiments(id),
  primary_account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id),
  market TEXT NOT NULL, locale TEXT NOT NULL, state_version INT NOT NULL DEFAULT 1 CHECK (state_version > 0),
  rules JSONB NOT NULL DEFAULT '{}'::jsonb, budget JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS affiliate.content_extensions (
  content_id BIGINT PRIMARY KEY REFERENCES public.content(id),
  experiment_id BIGINT NOT NULL REFERENCES public.experiments(id),
  primary_category TEXT NOT NULL, locale TEXT NOT NULL, target_market TEXT NOT NULL, publisher_owner TEXT NOT NULL,
  UNIQUE (content_id, experiment_id)
);

CREATE TABLE IF NOT EXISTS affiliate.content_revisions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  content_id BIGINT NOT NULL REFERENCES affiliate.content_extensions(content_id),
  revision_no INT NOT NULL CHECK (revision_no > 0), body_text TEXT NOT NULL, body_sha256 CHAR(64) NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb, template_version TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (content_id, revision_no)
);

CREATE TABLE IF NOT EXISTS affiliate.offers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id), external_item_id TEXT NOT NULL, destination_url TEXT NOT NULL,
  current_state TEXT NOT NULL DEFAULT 'unknown', checked_at TIMESTAMPTZ, UNIQUE (account_id, external_item_id)
);

CREATE TABLE IF NOT EXISTS affiliate.link_versions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  revision_id BIGINT NOT NULL REFERENCES affiliate.content_revisions(id), offer_id BIGINT NOT NULL REFERENCES affiliate.offers(id),
  placement_key TEXT NOT NULL, affiliate_url TEXT NOT NULL, policy_version_id BIGINT NOT NULL REFERENCES affiliate.policy_versions(id),
  tracking_key TEXT, evidence_ref TEXT NOT NULL, UNIQUE (revision_id, placement_key)
);

CREATE TABLE IF NOT EXISTS affiliate.tracking_bindings (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id), tracking_key TEXT NOT NULL,
  content_id BIGINT REFERENCES affiliate.content_extensions(content_id), experiment_id BIGINT REFERENCES public.experiments(id),
  valid_from TIMESTAMPTZ NOT NULL, valid_to TIMESTAMPTZ, evidence_ref TEXT NOT NULL,
  CHECK (valid_to IS NULL OR valid_from < valid_to), CHECK (content_id IS NOT NULL OR experiment_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS affiliate.import_batches (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id), policy_version_id BIGINT NOT NULL REFERENCES affiliate.policy_versions(id),
  report_family TEXT NOT NULL, file_hash CHAR(64) NOT NULL CHECK (file_hash ~ '^[0-9a-f]{64}$'), source_ref TEXT NOT NULL,
  period_start DATE NOT NULL, period_end DATE NOT NULL, captured_at TIMESTAMPTZ NOT NULL, provider_revision TEXT,
  state TEXT NOT NULL DEFAULT 'received' CHECK (state IN ('received','normalized','quarantined','posted','stale','conflict','failed')),
  data_quality TEXT NOT NULL DEFAULT 'available' CHECK (data_quality IN ('available','partial','unavailable')),
  UNIQUE (account_id, report_family, file_hash, policy_version_id), CHECK (period_start < period_end)
);

CREATE TABLE IF NOT EXISTS affiliate.fact_series (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id), family TEXT NOT NULL, series_key TEXT NOT NULL,
  grain TEXT NOT NULL, currency CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'), current_version_id BIGINT,
  UNIQUE (account_id, family, series_key)
);

CREATE TABLE IF NOT EXISTS affiliate.fact_versions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  series_id BIGINT NOT NULL REFERENCES affiliate.fact_series(id), batch_id BIGINT NOT NULL REFERENCES affiliate.import_batches(id),
  version_key TEXT NOT NULL, content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'), raw_status TEXT NOT NULL,
  event_date DATE NOT NULL, pending_balance NUMERIC(20,6) NOT NULL DEFAULT 0, confirmed_cumulative NUMERIC(20,6) NOT NULL DEFAULT 0,
  source_row_ref TEXT NOT NULL, attribution JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (series_id, version_key)
);

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fact_series_current_fk') THEN
    ALTER TABLE affiliate.fact_series ADD CONSTRAINT fact_series_current_fk FOREIGN KEY (current_version_id) REFERENCES affiliate.fact_versions(id);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS affiliate.journal_entries (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id), series_id BIGINT NOT NULL REFERENCES affiliate.fact_series(id),
  fact_version_id BIGINT NOT NULL REFERENCES affiliate.fact_versions(id), bucket TEXT NOT NULL CHECK (bucket IN ('pending','confirmed')),
  delta NUMERIC(20,6) NOT NULL, currency CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'), economic_date DATE NOT NULL,
  posted_at TIMESTAMPTZ NOT NULL DEFAULT now(), source_key TEXT NOT NULL UNIQUE, attribution JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS affiliate.payouts (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id),
  external_payout_id TEXT NOT NULL, currency CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'), current_version INT NOT NULL DEFAULT 1,
  latest_components JSONB NOT NULL DEFAULT '{}'::jsonb, evidence_ref TEXT NOT NULL, UNIQUE (account_id, external_payout_id)
);

CREATE TABLE IF NOT EXISTS affiliate.payout_adjustments (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, payout_id BIGINT NOT NULL REFERENCES affiliate.payouts(id), version INT NOT NULL,
  cleared_delta NUMERIC(20,6) NOT NULL DEFAULT 0, withheld_delta NUMERIC(20,6) NOT NULL DEFAULT 0, fee_delta NUMERIC(20,6) NOT NULL DEFAULT 0,
  net_expected_delta NUMERIC(20,6) NOT NULL, evidence_ref TEXT NOT NULL, UNIQUE (payout_id, version)
);

CREATE TABLE IF NOT EXISTS affiliate.cash_movements (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, account_id BIGINT NOT NULL REFERENCES affiliate.program_accounts(id), payout_id BIGINT REFERENCES affiliate.payouts(id),
  external_statement_key TEXT NOT NULL, paid_at TIMESTAMPTZ NOT NULL, currency CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'), signed_amount NUMERIC(20,6) NOT NULL,
  evidence_ref TEXT NOT NULL, UNIQUE (account_id, external_statement_key)
);

CREATE TABLE IF NOT EXISTS affiliate.cost_entries (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, experiment_id BIGINT REFERENCES public.experiments(id), content_id BIGINT REFERENCES public.content(id),
  economic_date DATE NOT NULL, paid_at TIMESTAMPTZ, currency CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'), recognized_amount NUMERIC(20,6) NOT NULL DEFAULT 0,
  cash_outflow NUMERIC(20,6) NOT NULL DEFAULT 0, classification TEXT NOT NULL, evidence_ref TEXT NOT NULL, source_key TEXT NOT NULL UNIQUE
);
ALTER TABLE affiliate.cost_entries ADD COLUMN IF NOT EXISTS legacy_cost_id BIGINT REFERENCES public.cost(id);

CREATE TABLE IF NOT EXISTS affiliate.time_entries (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, experiment_id BIGINT REFERENCES public.experiments(id), content_id BIGINT REFERENCES public.content(id),
  occurred_at TIMESTAMPTZ NOT NULL, minutes INT NOT NULL CHECK (minutes >= 0), actor_role TEXT NOT NULL, activity TEXT NOT NULL, source_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS affiliate.jobs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, kind TEXT NOT NULL, job_key TEXT NOT NULL UNIQUE, payload_hash CHAR(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  state TEXT NOT NULL, attempt INT NOT NULL DEFAULT 0, max_attempts INT NOT NULL DEFAULT 3, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  lease_owner TEXT, lease_expires_at TIMESTAMPTZ, fence_token BIGINT NOT NULL DEFAULT 0, result_ref TEXT, correlation_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS affiliate.outbox (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, event_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, payload JSONB NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','sent','failed')), attempts INT NOT NULL DEFAULT 0, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(), sent_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS affiliate.pull_checkpoints (
  consumer_key TEXT PRIMARY KEY, cursor TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_success_at TIMESTAMPTZ, last_error_code TEXT
);

CREATE TABLE IF NOT EXISTS affiliate.approval_bindings (
  approval_id BIGINT PRIMARY KEY REFERENCES public.approvals(id), revision_id BIGINT NOT NULL REFERENCES affiliate.content_revisions(id),
  policy_version_id BIGINT NOT NULL REFERENCES affiliate.policy_versions(id), artifact_hash CHAR(64) NOT NULL CHECK (artifact_hash ~ '^[0-9a-f]{64}$'),
  target TEXT NOT NULL, action TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, consumed_publication_id BIGINT
);

CREATE TABLE IF NOT EXISTS affiliate.approval_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, approval_id BIGINT NOT NULL REFERENCES public.approvals(id), update_key TEXT NOT NULL UNIQUE,
  actor_ref TEXT NOT NULL, requested_transition TEXT NOT NULL, result TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS affiliate.publications (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, revision_id BIGINT NOT NULL REFERENCES affiliate.content_revisions(id), approval_id BIGINT NOT NULL REFERENCES public.approvals(id),
  target TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, state TEXT NOT NULL, artifact_hash CHAR(64) NOT NULL CHECK (artifact_hash ~ '^[0-9a-f]{64}$'),
  git_commit TEXT, external_deployment_id TEXT, public_url TEXT, verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS affiliate.click_events (
  event_id UUID PRIMARY KEY, link_id BIGINT REFERENCES affiliate.link_versions(id), revision_id BIGINT NOT NULL REFERENCES affiliate.content_revisions(id),
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(), occurred_at TIMESTAMPTZ NOT NULL, session_token TEXT, qualification TEXT NOT NULL, ingest_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS affiliate.attribution_revisions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, event_id UUID NOT NULL REFERENCES affiliate.click_events(event_id),
  revision_no INT NOT NULL, attribution JSONB NOT NULL, reason TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (event_id, revision_no)
);

CREATE OR REPLACE FUNCTION affiliate.post_fact_version(
  p_batch_id BIGINT, p_series_id BIGINT, p_version_key TEXT, p_content_hash CHAR(64), p_event_date DATE,
  p_raw_status TEXT, p_pending NUMERIC, p_confirmed NUMERIC, p_currency CHAR(3), p_source_row_ref TEXT, p_attribution JSONB DEFAULT '{}'::jsonb
) RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE old affiliate.fact_versions%ROWTYPE; new_id BIGINT; account BIGINT;
BEGIN
  SELECT fs.account_id INTO account FROM affiliate.fact_series fs WHERE fs.id = p_series_id FOR UPDATE;
  IF account IS NULL THEN RAISE EXCEPTION 'unknown fact series %', p_series_id; END IF;
  IF NOT EXISTS (SELECT 1 FROM affiliate.fact_series WHERE id=p_series_id AND currency=p_currency) THEN
    RAISE EXCEPTION 'currency % does not match series %', p_currency, p_series_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM affiliate.import_batches WHERE id=p_batch_id AND account_id=account AND state IN ('normalized','received')) THEN
    RAISE EXCEPTION 'batch % is not ready for posting', p_batch_id;
  END IF;
  SELECT fv.* INTO old FROM affiliate.fact_versions fv WHERE fv.series_id=p_series_id AND fv.version_key=p_version_key;
  IF FOUND THEN
    IF old.content_hash = p_content_hash THEN RETURN old.id; END IF;
    RAISE EXCEPTION 'conflicting content hash for series %, version %', p_series_id, p_version_key;
  END IF;
  SELECT fv.* INTO old FROM affiliate.fact_versions fv JOIN affiliate.fact_series fs ON fs.current_version_id=fv.id WHERE fs.id=p_series_id;
  INSERT INTO affiliate.fact_versions(series_id,batch_id,version_key,content_hash,raw_status,event_date,pending_balance,confirmed_cumulative,source_row_ref,attribution)
  VALUES(p_series_id,p_batch_id,p_version_key,p_content_hash,p_raw_status,p_event_date,p_pending,p_confirmed,p_source_row_ref,p_attribution) RETURNING id INTO new_id;
  IF p_pending - COALESCE(old.pending_balance,0) <> 0 THEN
    INSERT INTO affiliate.journal_entries(account_id,series_id,fact_version_id,bucket,delta,currency,economic_date,source_key,attribution)
    VALUES(account,p_series_id,new_id,'pending',p_pending-COALESCE(old.pending_balance,0),p_currency,p_event_date,p_series_id||':'||p_version_key||':pending',p_attribution);
  END IF;
  IF p_confirmed - COALESCE(old.confirmed_cumulative,0) <> 0 THEN
    INSERT INTO affiliate.journal_entries(account_id,series_id,fact_version_id,bucket,delta,currency,economic_date,source_key,attribution)
    VALUES(account,p_series_id,new_id,'confirmed',p_confirmed-COALESCE(old.confirmed_cumulative,0),p_currency,p_event_date,p_series_id||':'||p_version_key||':confirmed',p_attribution);
  END IF;
  UPDATE affiliate.fact_series SET current_version_id=new_id WHERE id=p_series_id;
  RETURN new_id;
END $$;

CREATE OR REPLACE VIEW affiliate.v_program_balances AS
SELECT account_id, currency, bucket, sum(delta) AS amount FROM affiliate.journal_entries GROUP BY account_id,currency,bucket;

CREATE OR REPLACE VIEW affiliate.v_content_economics AS
SELECT cr.content_id, coalesce(sum(je.delta) FILTER (WHERE je.bucket='confirmed'),0) AS confirmed_amount
FROM affiliate.content_revisions cr LEFT JOIN affiliate.journal_entries je ON CASE WHEN je.attribution->>'content_id' ~ '^[0-9]+$' THEN (je.attribution->>'content_id')::bigint END = cr.content_id GROUP BY cr.content_id;

CREATE OR REPLACE VIEW affiliate.v_experiment_economics AS
SELECT ce.experiment_id, coalesce(sum(je.delta) FILTER (WHERE je.bucket='confirmed'),0) AS confirmed_amount
FROM affiliate.content_extensions ce LEFT JOIN affiliate.journal_entries je ON CASE WHEN je.attribution->>'experiment_id' ~ '^[0-9]+$' THEN (je.attribution->>'experiment_id')::bigint END = ce.experiment_id GROUP BY ce.experiment_id;

CREATE OR REPLACE VIEW affiliate.v_cash_flow AS
SELECT account_id, currency, sum(signed_amount) AS cash_amount FROM affiliate.cash_movements GROUP BY account_id,currency;

CREATE OR REPLACE VIEW affiliate.v_data_readiness AS
SELECT account_id, report_family, data_quality, count(*) AS batches FROM affiliate.import_batches GROUP BY account_id,report_family,data_quality;
