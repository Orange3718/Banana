#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
uid="$(id -u)"
agent="$HOME/Library/LaunchAgents/com.atemoya.revenue-reconciler.plist"

test "$(git -C "$repo_root" branch --show-current)" != "main" || {
  echo "Refusing to install from main; use the reviewed feature branch." >&2
  exit 1
}

"$repo_root/ops/scripts/backup.sh"
"$repo_root/ops/scripts/apply-migrations.sh"

for workflow in AtemoyaRevenueAutopilot01 AtemoyaOpsGuardian01; do
  docker cp "$repo_root/n8n/workflows/exports/$workflow.json" "atemoya-n8n:/tmp/$workflow.json"
  docker exec atemoya-n8n n8n import:workflow --input="/tmp/$workflow.json"
  docker exec atemoya-n8n n8n publish:workflow --id="$workflow"
done

install -m 0644 "$repo_root/ops/launchd/com.atemoya.revenue-reconciler.plist" "$agent"
launchctl bootout "gui/$uid/com.atemoya.revenue-reconciler" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$agent"

docker restart atemoya-n8n >/dev/null
for _ in {1..30}; do
  curl -fsS http://127.0.0.1:5678/healthz >/dev/null 2>&1 && break
  sleep 1
done
launchctl kickstart -k "gui/$uid/com.atemoya.local-llm-status"
launchctl kickstart -k "gui/$uid/com.atemoya.revenue-reconciler"
"$repo_root/ops/scripts/verify.sh"
echo "Revenue operations installation: PASS"
