#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
for migration in "$repo_root"/db/migrations/*.sql; do
  echo "Applying $(basename "$migration")"
  docker exec -i atemoya-postgres sh -lc \
    'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$migration"
done
