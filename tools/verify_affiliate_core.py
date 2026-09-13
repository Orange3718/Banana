#!/usr/bin/env python3
"""Transactional acceptance tests for affiliate migration 013."""
import subprocess
import sys

PSQL = ["docker", "exec", "-i", "atemoya-postgres", "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "n8n", "-d", "n8n", "-At"]

SQL = r"""
BEGIN;
INSERT INTO affiliate.program_accounts(environment,provider,account_ref,market,state)
VALUES ('test','fixture','fixture-core-test','US','ready') RETURNING id
\gset account_
INSERT INTO affiliate.policy_versions(account_id,version,source_ref,verified_at,capabilities,contract)
VALUES (:account_id,1,'fixture://policy',now(),'{}','{}') RETURNING id
\gset policy_
INSERT INTO affiliate.import_batches(account_id,policy_version_id,report_family,file_hash,source_ref,period_start,period_end,captured_at,state)
VALUES (:account_id,:policy_id,'fixture','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','fixture://batch','2026-01-01','2026-01-02',now(),'normalized') RETURNING id
\gset batch_
INSERT INTO affiliate.fact_series(account_id,family,series_key,grain,currency)
VALUES (:account_id,'commission','fixture-series','daily','USD') RETURNING id
\gset series_
SELECT affiliate.post_fact_version(:batch_id,:series_id,'v1','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','2026-01-01','reported',10000,0,'USD','row-1','{}') AS first_id;
SELECT CASE WHEN (SELECT count(*) FROM affiliate.journal_entries WHERE series_id=:series_id)=1 THEN 'F01 pending journal ok' ELSE 'FAIL F01' END;
SELECT affiliate.post_fact_version(:batch_id,:series_id,'v2','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','2026-01-01','reported',0,10000,'USD','row-2','{}') AS second_id;
SELECT CASE WHEN (SELECT coalesce(sum(delta),0) FROM affiliate.journal_entries WHERE series_id=:series_id AND bucket='pending')=0 AND (SELECT coalesce(sum(delta),0) FROM affiliate.journal_entries WHERE series_id=:series_id AND bucket='confirmed')=10000 THEN 'F02 delta posting ok' ELSE 'FAIL F02' END;
SELECT CASE WHEN affiliate.post_fact_version(:batch_id,:series_id,'v2','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','2026-01-01','reported',0,10000,'USD','row-2','{}')=(SELECT current_version_id FROM affiliate.fact_series WHERE id=:series_id) THEN 'F03 idempotent replay ok' ELSE 'FAIL F03' END;
SELECT affiliate.post_fact_version(:batch_id,:series_id,'v3','dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd','2026-01-01','reported',0,8000,'USD','row-3','{}');
SELECT CASE WHEN (SELECT coalesce(sum(delta),0) FROM affiliate.journal_entries WHERE series_id=:series_id AND bucket='confirmed')=8000 THEN 'F04 reversal delta ok' ELSE 'FAIL F04' END;
INSERT INTO affiliate.payouts(account_id,external_payout_id,currency,evidence_ref) VALUES (:account_id,'fixture-payout','USD','fixture://payout') RETURNING id
\gset payout_
INSERT INTO affiliate.cash_movements(account_id,payout_id,external_statement_key,paid_at,currency,signed_amount,evidence_ref) VALUES (:account_id,:payout_id,'fixture-statement',now(),'USD',7500,'fixture://statement');
SELECT CASE WHEN (SELECT cash_amount FROM affiliate.v_cash_flow WHERE account_id=:account_id AND currency='USD')=7500 THEN 'F05 cash view ok' ELSE 'FAIL F05' END;
DO $$ BEGIN
  BEGIN
    PERFORM affiliate.post_fact_version((SELECT ib.id FROM affiliate.import_batches ib WHERE ib.source_ref='fixture://batch'),(SELECT fs.id FROM affiliate.fact_series fs WHERE fs.series_key='fixture-series'),'v4','eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','2026-01-01','reported',0,1,'EUR','row-4','{}');
    RAISE EXCEPTION 'expected currency failure';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM NOT LIKE 'currency % does not match series %' THEN RAISE; END IF;
  END;
END $$;
SELECT 'F06 currency guard ok';
INSERT INTO affiliate.outbox(event_key,kind,payload) VALUES ('fixture-event','fixture','{}');
INSERT INTO affiliate.pull_checkpoints(consumer_key,cursor) VALUES ('fixture-consumer','cursor-1');
INSERT INTO affiliate.time_entries(experiment_id,occurred_at,minutes,actor_role,activity,source_key) VALUES (NULL,now(),15,'operator','fixture','fixture-time');
SELECT CASE WHEN (SELECT count(*) FROM affiliate.outbox WHERE event_key='fixture-event')=1 AND (SELECT cursor FROM affiliate.pull_checkpoints WHERE consumer_key='fixture-consumer')='cursor-1' THEN 'F07 delivery controls ok' ELSE 'FAIL F07' END;
ROLLBACK;
"""

proc = subprocess.run(PSQL, input=SQL, text=True, capture_output=True)
if proc.returncode:
    print(proc.stderr, file=sys.stderr)
    sys.exit(proc.returncode)
lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
expected = ["F01 pending journal ok", "F02 delta posting ok", "F03 idempotent replay ok", "F04 reversal delta ok", "F05 cash view ok", "F06 currency guard ok", "F07 delivery controls ok"]
missing = [item for item in expected if item not in lines]
if missing:
    print("missing acceptance markers:", ", ".join(missing), file=sys.stderr)
    print(proc.stdout, file=sys.stderr)
    sys.exit(1)
print("affiliate core acceptance: PASS")
for item in expected:
    print(item)
