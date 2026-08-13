#!/usr/bin/env bash
set -euo pipefail

backup_root="${ATEMOYA_BACKUP_DIR:-$HOME/Atemoya/backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="$backup_root/$stamp"
mkdir -p "$destination/workflows"
chmod 700 "$backup_root" "$destination"

docker exec atemoya-postgres sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$destination/postgres.dump"
chmod 600 "$destination/postgres.dump"

docker exec atemoya-n8n rm -rf /tmp/atemoya-workflow-export
docker exec atemoya-n8n n8n export:workflow --backup --output=/tmp/atemoya-workflow-export >/dev/null
docker cp atemoya-n8n:/tmp/atemoya-workflow-export/. "$destination/workflows/" >/dev/null
docker exec atemoya-n8n rm -rf /tmp/atemoya-workflow-export

test -s "$destination/postgres.dump"
find "$destination/workflows" -type f -name '*.json' -size +0 | grep -q .
printf '%s\n' "$destination"
