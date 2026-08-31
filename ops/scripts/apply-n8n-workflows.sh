#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
export_dir="$repo_root/n8n/workflows/exports"
container="${ATEMOYA_N8N_CONTAINER:-atemoya-n8n}"
project_id="${ATEMOYA_N8N_PROJECT_ID:-gCPKSdTG43Imn6aD}"

if [[ $# -eq 0 ]]; then
  echo "usage: $0 workflow-export.json [workflow-export.json ...]" >&2
  exit 2
fi

docker exec "$container" n8n --version >/dev/null

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

for input in "$@"; do
  case "$input" in
    /*) source_path="$input" ;;
    *) source_path="$export_dir/$input" ;;
  esac
  if [[ ! -r "$source_path" ]]; then
    echo "workflow export not readable: $source_path" >&2
    exit 1
  fi
  python3 -m json.tool "$source_path" >/dev/null
  base_name="$(basename "$source_path")"
  container_path="/tmp/atemoya-workflow-$base_name"
  cp "$source_path" "$tmp_dir/$base_name"
  docker cp "$tmp_dir/$base_name" "$container:$container_path"
  workflow_id="$(python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); wf=data[0] if isinstance(data,list) else data; print(wf["id"])' "$source_path")"
  workflow_active="$(python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); wf=data[0] if isinstance(data,list) else data; print("true" if wf.get("active") else "false")' "$source_path")"
  docker exec "$container" n8n import:workflow \
    --input="$container_path" \
    --projectId="$project_id"
  if [[ "$workflow_active" == "true" ]]; then
    docker exec "$container" n8n update:workflow --id="$workflow_id" --active=true >/dev/null
    docker exec "$container" n8n publish:workflow --id="$workflow_id" >/dev/null || true
  fi
  docker exec "$container" rm -f "$container_path" >/dev/null 2>&1 || true
  echo "applied $base_name id=$workflow_id active=$workflow_active"
done
