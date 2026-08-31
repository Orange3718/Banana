#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"

echo "Atemoya preflight"
echo "repo: $repo_root"
git -C "$repo_root" status --short --branch

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

echo
echo "recent n8n failures"
python3 - <<'PY' || true
import json
import subprocess

sql = """select coalesce(json_agg(x),'[]'::json) from (
select e.id as execution_id,w.name as workflow,e.status,e."startedAt" as started_at,ed.data as data
from execution_entity e
join workflow_entity w on w.id=e."workflowId"
left join execution_data ed on ed."executionId"=e.id
where e.status='error'
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

for row in json.loads(raw or "[]"):
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
    print(f"{row.get('execution_id')}\t{row.get('workflow')}\t{row.get('status')}\t{last_node}\t{message[:240]}")
PY

echo
echo "Atemoya preflight: PASS"
