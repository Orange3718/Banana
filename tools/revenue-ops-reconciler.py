#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconcile Atemoya revenue stages and alert on business-output stalls."""
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB_CMD = ["/usr/local/bin/docker", "exec", "atemoya-postgres", "psql", "-U", "n8n", "-d", "n8n", "-At"]
STATE_FILE = ROOT / "tools/revenue-ops-reconciler-state.json"
AUTOPILOT_URL = "http://127.0.0.1:5678/webhook/atemoya-revenue-autopilot-run"
INCIDENT_URL = "http://127.0.0.1:5678/webhook/atemoya-ops-incident"


def command(args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def db(statement):
    result = command(DB_CMD + ["-c", statement])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PostgreSQL query failed")
    return result.stdout.strip()


def db_json(statement):
    raw = db("SELECT row_to_json(x) FROM (" + statement + ") x;")
    return json.loads(raw or "{}")


def post(url, payload=None, timeout=10):
    data = json.dumps(payload or {}, ensure_ascii=False).encode()
    with urlopen(Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=timeout) as response:
        return 200 <= response.status < 300


def assess(facts):
    oldest = int(facts.get("oldest_actionable_minutes") or 0)
    pending = int(facts.get("pending_approval_minutes") or 0)
    if oldest >= 72 * 60 or pending >= 72 * 60:
        return "bad", "수익 파이프라인이 72시간 이상 결과 없이 정체됨"
    if int(facts.get("published_7d") or 0) == 0 or oldest >= 24 * 60 or pending >= 24 * 60:
        return "review", "최근 7일 게시가 없거나 수익 파이프라인이 24시간 이상 정체됨"
    return "good", "수익 파이프라인이 SLA 안에서 진행 중"


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    db("UPDATE revenue_autopilot_jobs j SET stage=CASE WHEN a.status='approved' THEN 'approved' WHEN a.status IN ('rejected','deferred') THEN 'rejected' ELSE j.stage END,updated_at=NOW(),finished_at=CASE WHEN a.status IN ('rejected','deferred') THEN NOW() ELSE j.finished_at END FROM approval_requests a WHERE a.id=j.approval_request_id AND j.stage='awaiting_approval' AND a.status<>'pending'; UPDATE revenue_autopilot_jobs SET stage=CASE WHEN attempt>=max_attempts THEN 'failed' ELSE 'retry' END,next_attempt_at=NOW()+interval '1 hour',last_error='reconciler recovered stale lease',updated_at=NOW() WHERE stage IN ('running','rendering') AND updated_at<NOW()-interval '45 minutes';")
    facts = db_json("SELECT count(*) FILTER(WHERE stage='queued')::int AS queued,count(*) FILTER(WHERE stage='retry')::int AS retry,count(*) FILTER(WHERE stage='awaiting_approval')::int AS awaiting_approval,count(*) FILTER(WHERE stage='approved')::int AS approved,count(*) FILTER(WHERE stage='branch_ready')::int AS branch_ready,count(*) FILTER(WHERE stage='published')::int AS published_total,COALESCE((SELECT EXTRACT(EPOCH FROM (NOW()-min(x.created_at)))/60 FROM revenue_autopilot_jobs x WHERE x.stage IN ('queued','retry','awaiting_approval','approved','rendering','branch_ready')),0)::int AS oldest_actionable_minutes,COALESCE((SELECT EXTRACT(EPOCH FROM (NOW()-min(a.requested_at)))/60 FROM approval_requests a WHERE a.request_type='revenue_content_publish' AND a.status='pending'),0)::int AS pending_approval_minutes,(SELECT count(*) FROM content WHERE published_at>NOW()-interval '7 days' AND published_url IS NOT NULL)::int AS published_7d,COALESCE((SELECT sum(page_views) FROM revenue_channel_metrics WHERE metric_date>=CURRENT_DATE-6),0)::int AS views_7d,COALESCE((SELECT sum(affiliate_clicks) FROM revenue_channel_metrics WHERE metric_date>=CURRENT_DATE-6),0)::int AS affiliate_clicks_7d,COALESCE((SELECT sum(amount) FROM revenue WHERE occurred_on>=CURRENT_DATE-6),0) AS revenue_7d FROM revenue_autopilot_jobs")
    actions = []
    if int(facts.get("approved") or 0):
        result = command(["/bin/launchctl", "kickstart", "-k", "gui/%s/com.atemoya.autopilot-publisher" % os.getuid()])
        if result.returncode == 0:
            actions.append("publisher_kickstarted")
    active = sum(int(facts.get(key) or 0) for key in ("awaiting_approval", "approved", "branch_ready"))
    if active == 0 and int(facts.get("queued") or 0) + int(facts.get("retry") or 0) > 0:
        try:
            if post(AUTOPILOT_URL):
                actions.append("autopilot_triggered")
        except Exception as exc:
            actions.append("autopilot_trigger_failed:" + str(exc)[:120])
    status, reason = assess(facts)
    db("INSERT INTO revenue_autopilot_reconciliations(status,action,facts) VALUES('%s','%s','%s'::jsonb);" % (status, ",".join(actions).replace("'", "''"), json.dumps(facts, ensure_ascii=False).replace("'", "''")))
    state = load_state()
    if state.get("status") != status:
        try:
            post(INCIDENT_URL, {"status": status.upper(), "summary": reason + "\n" + json.dumps(facts, ensure_ascii=False), "source": "revenue-ops-reconciler"})
        except Exception:
            pass
    save_state({"status": status, "reason": reason, "facts": facts, "actions": actions, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(json.dumps({"status": status, "reason": reason, "facts": facts, "actions": actions}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
