#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

test "$(git -C "$repo_root" branch --show-current)" != "main" || {
  echo "Refusing to install from main; use the reviewed feature branch." >&2
  exit 1
}

"$repo_root/ops/scripts/backup.sh"
python3 "$repo_root/tools/merge-telegram-review-router.py"

docker cp "$repo_root/n8n/workflows/exports/AtemoyaLocalLLMReviewGate01.json" atemoya-n8n:/tmp/AtemoyaLocalLLMReviewGate01.json
docker cp "$repo_root/n8n/workflows/exports/AtemoyaTelegramMemory01.json" atemoya-n8n:/tmp/AtemoyaTelegramMemory01.json
docker exec atemoya-n8n n8n unpublish:workflow --id=AtemoyaLocalLLMReviewGate01
docker exec atemoya-n8n n8n import:workflow --input=/tmp/AtemoyaTelegramMemory01.json
docker exec atemoya-n8n n8n publish:workflow --id=AtemoyaTelegramMemory01
docker restart atemoya-n8n >/dev/null

for _ in {1..30}; do
  curl -fsS http://127.0.0.1:5678/healthz >/dev/null 2>&1 && break
  sleep 1
done

active_count="$(docker exec atemoya-postgres psql -U n8n -d n8n -Atc "SELECT count(*) FROM workflow_entity WHERE active AND nodes::text ILIKE '%telegramTrigger%';")"
test "$active_count" = "1" || {
  echo "Expected one active Telegram trigger, found $active_count" >&2
  exit 1
}

echo "Telegram inbound router installation: PASS"
