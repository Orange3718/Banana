#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -x .venv-next/bin/python ]] || { echo "Run bash tools/setup_macos.sh first."; exit 1; }
.venv-next/bin/python -m neural.preflight
bash tools/start_neural.sh
echo "Read SESSION_HANDOFF.md before making changes."
