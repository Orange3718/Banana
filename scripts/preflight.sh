#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

echo "Atemoya preflight"
echo "repo: $repo_root"
git -C "$repo_root" status --short --branch

echo "contract: $repo_root/docs/OPERATING_CONTRACT.md"

echo
echo "workflow scope"
python3 - "$repo_root/ops/business-scope-20261101.json" <<'PY'
import json
import subprocess
import sys

scope = json.load(open(sys.argv[1]))
ids = scope['parked_workflows']
assert all(value.startswith('Atemoya') and value.endswith('01') and value.isalnum() for value in ids)
literal = ','.join("'" + value + "'" for value in ids)
sql = f"SELECT count(*) FROM workflow_entity WHERE active; SELECT id,active FROM workflow_entity WHERE id IN ({literal}) ORDER BY id;"
result = subprocess.run(['docker','exec','atemoya-postgres','psql','-U','n8n','-d','n8n','-At','-c',sql],text=True,capture_output=True,check=True)
rows = result.stdout.strip().splitlines()
print('active n8n workflows:', rows[0])
print('parked workflows:', ', '.join(rows[1:]))
if any(row.endswith('|t') for row in rows[1:]):
    raise SystemExit('Parked workflow is active')
PY

echo
echo "docker containers"
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E '^(atemoya-postgres|atemoya-n8n|atemoya-webhook-proxy)\b' || true

echo
echo "n8n health"
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:5678/healthz
echo

echo
echo "postgres health"
docker exec atemoya-postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

echo
echo "ollama models"
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:11434/api/tags |
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(", ".join(m.get("name","") for m in data.get("models",[])) or "no models")'

echo
echo "launch agents"
for label in \
  com.atemoya.local-llm \
  com.atemoya.source-scout \
  com.atemoya.ops-watchdog \
  com.atemoya.revenue-reconciler \
  com.atemoya.affiliate-direct-publisher \
  com.atemoya.autopilot-publisher \
  com.atemoya.local-llm-status \
  com.atemoya.obsidian-inbox
do
  if launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1; then
    state="$(launchctl print "gui/$(id -u)/$label" 2>/dev/null | awk -F'= ' '/state =/{print $2; exit}')"
    runs="$(launchctl print "gui/$(id -u)/$label" 2>/dev/null | awk -F'= ' '/runs =/{print $2; exit}')"
    echo "$label registered state=${state:-unknown} runs=${runs:-unknown}"
  else
    echo "$label not-registered"
  fi
done

python3 - "$repo_root/ops/business-scope-20261101.json" <<'PY'
import json
import os
import subprocess
import sys
scope = json.load(open(sys.argv[1]))
for label in scope.get('parked_launch_agents', []):
    result = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/{label}'], capture_output=True)
    print(f'parked launch agent: {label} registered={result.returncode == 0}')
    if result.returncode == 0:
        raise SystemExit(f'Parked launch agent is active: {label}')
PY

echo
echo "direct affiliate publication"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "SELECT state,count(*) FROM affiliate.jobs WHERE kind='direct_affiliate_publish' GROUP BY state ORDER BY state;"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "SELECT state,count(*) FROM affiliate.publications GROUP BY state ORDER BY state;"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "
SELECT scheduled_at,category,title,publication_state,attempt,public_url,last_error
FROM affiliate.v_direct_publication_status
ORDER BY scheduled_at;"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "
SELECT id,active,\"activeVersionId\" FROM workflow_entity WHERE id='AtemoyaRevenueAutopilot01';"

echo
echo "measurement and delivery gaps"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "
SELECT 'click_events' AS item,count(*) AS rows FROM affiliate.click_events
UNION ALL SELECT 'import_batches',count(*) FROM affiliate.import_batches
UNION ALL SELECT 'journal_entries',count(*) FROM affiliate.journal_entries
UNION ALL SELECT 'cash_movements',count(*) FROM affiliate.cash_movements
UNION ALL SELECT 'cost_entries',count(*) FROM affiliate.cost_entries
UNION ALL SELECT 'time_entries',count(*) FROM affiliate.time_entries;"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "SELECT kind,state,count(*) FROM affiliate.outbox GROUP BY kind,state ORDER BY kind,state;"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "SELECT max(received_at) AS last_received,count(*) AS total FROM telegram_memory WHERE chat_id>0;"
docker exec atemoya-postgres psql -U n8n -d n8n -P pager=off -c "SELECT id,active FROM workflow_entity WHERE nodes::text ILIKE '%telegramTrigger%';"

echo
echo "n8n failures in last 24 hours"
python3 - <<'PY' || true
import json
import subprocess

sql = """select coalesce(json_agg(x),'[]'::json) from (
select e.id as execution_id,w.name as workflow,e.status,e."startedAt" as started_at,ed.data as data
from execution_entity e
join workflow_entity w on w.id=e."workflowId"
left join execution_data ed on ed."executionId"=e.id
where e.status='error' and e."startedAt" >= now() - interval '24 hours'
order by e.id desc
limit 5
) x;"""
raw = subprocess.check_output(
    ["docker", "exec", "atemoya-postgres", "psql", "-U", "n8n", "-d", "n8n", "-At", "-c", sql],
    text=True,
)

def deref(value, root):
    for _ in range(20):
        if isinstance(value, str) and value.isdigit():
            idx = int(value)
            if 0 <= idx < len(root):
                value = root[idx]
                continue
        break
    return value

rows = json.loads(raw or "[]")
if not rows:
    print("none")
for row in rows:
    last_node = ""
    message = ""
    try:
        root = json.loads(row.get("data") or "[]")
        top = deref(root[0], root) if isinstance(root, list) and root else {}
        result = deref(top.get("resultData"), root) if isinstance(top, dict) else {}
        last_node = str(deref(result.get("lastNodeExecuted"), root) or "") if isinstance(result, dict) else ""
        error = deref(result.get("error"), root) if isinstance(result, dict) else {}
        if isinstance(error, dict):
            message = str(deref(error.get("description"), root) or deref(error.get("message"), root) or deref(error.get("name"), root) or "")
    except Exception as exc:
        message = str(exc)
    print(f"{row.get('execution_id')}\t{row.get('started_at')}\t{row.get('workflow')}\t{last_node}\t{message[:240]}")
PY

echo
echo "Atemoya preflight: checks completed; not end-to-end workload acceptance. Review errors above."
