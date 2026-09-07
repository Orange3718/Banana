#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null || { echo "Python 3 is required."; exit 1; }
command -v npm >/dev/null || { echo "Node.js 22 and npm are required."; exit 1; }

python3 -m venv .venv-next
.venv-next/bin/python -m pip install --upgrade pip
.venv-next/bin/python -m pip install -r next_requirements.txt

cd apps/dashboard
npm ci
npm run build
cd "$ROOT"

mkdir -p next_data/run next_data/logs
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created .env from .env.example. Add keys locally when the trusted IP is ready."
else
  chmod 600 .env
  echo "Existing .env preserved."
fi

echo "Setup complete. Run: bash tools/start_neural.sh"
echo "Preflight check: .venv-next/bin/python -m neural.preflight"
