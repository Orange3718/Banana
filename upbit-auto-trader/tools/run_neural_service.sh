#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv-next/bin/python"
SERVICE="${1:-api}"

cd "$ROOT"
[[ -x "$PYTHON" ]] || { echo "Run bash tools/setup_macos.sh first."; exit 1; }

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi

NEURAL_PORT="${NEURAL_PORT:-8765}"
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://127.0.0.1:${NEURAL_PORT}}"

case "$SERVICE" in
  api)
    exec "$PYTHON" -m uvicorn neural.api:create_app --factory --host 127.0.0.1 --port "$NEURAL_PORT"
    ;;
  upbit-collector)
    exec "$PYTHON" -m neural.collector
    ;;
  binance-futures-collector)
    exec "$PYTHON" -m neural.binance_futures
    ;;
  *)
    echo "Unknown service: $SERVICE" >&2
    exit 64
    ;;
esac
