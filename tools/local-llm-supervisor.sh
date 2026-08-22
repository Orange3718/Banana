#!/bin/zsh
set -u
ROOT="/Users/orange/Developer/Banana-atemoya-ops"
LOCK="/tmp/atemoya-local-llm.lock"
LOG="/tmp/atemoya-local-llm-supervisor.log"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date -Iseconds) skip: previous local LLM run is still active" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
echo "$(date -Iseconds) start" >> "$LOG"
cd "$ROOT" && /usr/bin/python3 tools/local-llm-runner.py >> "$LOG" 2>&1
echo "$(date -Iseconds) finish" >> "$LOG"
