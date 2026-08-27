#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
python3 -m json.tool "$repo_root/n8n/workflows/business-scout.json" >/dev/null
python3 -m json.tool "$repo_root/n8n/workflows/business-scout-error-handler.json" >/dev/null
python3 -m json.tool "$repo_root/n8n/workflows/atemoya-hardware-execution-orchestrator.json" >/dev/null
python3 -m json.tool "$repo_root/n8n/workflows/exports/AtemoyaOpsGuardian01.json" >/dev/null
python3 -m json.tool "$repo_root/n8n/workflows/exports/AtemoyaRevenueAutopilot01.json" >/dev/null
test -x "$repo_root/ops/scripts/export-obsidian-inbox.sh"
test -r "$repo_root/tools/ops-watchdog.py"
test -r "$repo_root/tools/autopilot-publisher.py"

docker compose --env-file "$repo_root/.env.example" -f "$repo_root/docker-compose.yml" config --quiet
docker exec atemoya-postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null
curl --fail --silent --show-error http://127.0.0.1:5678/ >/dev/null

expected='agent_actions approvals assets business_ideas content cost executions experiments revenue'
actual="$(docker exec atemoya-postgres sh -lc 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select table_name from information_schema.tables where table_schema='"'"'public'"'"' and table_name in ('"'"'business_ideas'"'"','"'"'experiments'"'"','"'"'assets'"'"','"'"'content'"'"','"'"'revenue'"'"','"'"'cost'"'"','"'"'executions'"'"','"'"'agent_actions'"'"','"'"'approvals'"'"') order by table_name"' | tr '\n' ' ' | sed 's/ $//')"
test "$actual" = "$expected" || { echo "Operational tables are incomplete: $actual" >&2; exit 1; }

guardian_expected='ops_daily_reviews system_health_checks system_incidents'
guardian_actual="$(docker exec atemoya-postgres sh -lc 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select table_name from information_schema.tables where table_schema='"'"'public'"'"' and table_name in ('"'"'system_health_checks'"'"','"'"'system_incidents'"'"','"'"'ops_daily_reviews'"'"') order by table_name"' | tr '\n' ' ' | sed 's/ $//')"
test "$guardian_actual" = "$guardian_expected" || { echo "Guardian tables are incomplete: $guardian_actual" >&2; exit 1; }

autopilot_expected='revenue_autopilot_jobs'
autopilot_actual="$(docker exec atemoya-postgres sh -lc 'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select table_name from information_schema.tables where table_schema='"'"'public'"'"' and table_name='"'"'revenue_autopilot_jobs'"'"'"')"
test "$autopilot_actual" = "$autopilot_expected" || { echo "Revenue Autopilot table is missing" >&2; exit 1; }
echo "Atemoya runtime verification: PASS"
