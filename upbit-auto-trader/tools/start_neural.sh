#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv-next/bin/python"
RUN_DIR="$ROOT/next_data/run"
LOG_DIR="$ROOT/next_data/logs"

[[ -x "$PYTHON" ]] || { echo "Run bash tools/setup_macos.sh first."; exit 1; }
mkdir -p "$RUN_DIR" "$LOG_DIR"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi
NEURAL_PORT="${NEURAL_PORT:-8765}"

start_process() {
  local name="$1"
  shift
  local pid_file="$RUN_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    return
  fi
  cd "$ROOT"
  nohup "$PYTHON" "$@" >"$LOG_DIR/$name.out.log" 2>"$LOG_DIR/$name.err.log" &
  echo $! >"$pid_file"
}

export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://127.0.0.1:${NEURAL_PORT}}"
start_process neural-api -m uvicorn neural.api:create_app --factory --host 127.0.0.1 --port "$NEURAL_PORT"
start_process upbit-collector -m neural.collector
start_process binance-futures-collector -m neural.binance_futures

echo "Neural Trade started: ${PUBLIC_BASE_URL}"
