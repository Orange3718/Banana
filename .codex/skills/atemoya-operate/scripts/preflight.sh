#!/bin/zsh
set -u
ROOT="/Users/orange/Developer/Banana-atemoya-ops"
cd "$ROOT" || exit 1
echo "branch=$(git branch --show-current) dirty=$(git status --porcelain | wc -l | tr -d ' ')"
echo "containers=$(/usr/local/bin/docker ps --format '{{.Names}}:{{.Status}}' | rg '^atemoya-' | paste -sd ',' -)"
echo "n8n=$(curl -fsS --max-time 3 http://127.0.0.1:5678/healthz 2>/dev/null || echo unavailable)"
echo "ollama=$(curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags 2>/dev/null | rg -o 'qwen3\.5:4b' | head -1 || echo unavailable)"
for label in com.atemoya.local-llm com.atemoya.source-scout com.atemoya.nightly-reflection com.atemoya.local-llm-status; do
  state=$(launchctl print "gui/$(id -u)/$label" 2>/dev/null | rg -m1 'state =' | sed 's/^[[:space:]]*//')
  runs=$(launchctl print "gui/$(id -u)/$label" 2>/dev/null | rg -m1 'runs =' | sed 's/^[[:space:]]*//')
  echo "$label=${state:-missing} ${runs:-}"
done
/usr/local/bin/docker exec atemoya-postgres psql -U n8n -d n8n -At -F '|' -c "SELECT 'llm_recent',status,count(*) FROM local_llm_runs WHERE updated_at>now()-interval '24 hours' GROUP BY status ORDER BY status;" 2>/dev/null || true
echo "local_llm_last=$(tail -1 /tmp/atemoya-local-llm-supervisor.log 2>/dev/null || echo none)"
echo "source_scout_last=$(tail -1 /tmp/atemoya-source-scout.out 2>/dev/null || echo none)"
echo "nightly_reflection_last=$(tail -1 /tmp/atemoya-nightly-reflection.out 2>/dev/null || echo none)"
