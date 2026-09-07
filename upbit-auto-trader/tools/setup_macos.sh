#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null || { echo "Python 3 is required."; exit 1; }
if command -v npm >/dev/null; then
  JS_INSTALL=(npm ci)
  JS_BUILD=(npm run build)
elif command -v pnpm >/dev/null; then
  JS_INSTALL=(pnpm install --frozen-lockfile=false)
  JS_BUILD=(pnpm run build)
else
  echo "Node.js 22 with npm or pnpm is required."
  exit 1
fi

python3 -m venv .venv-next
.venv-next/bin/python -m pip install --upgrade pip
.venv-next/bin/python -m pip install -r next_requirements.txt

cd apps/dashboard
"${JS_INSTALL[@]}"
"${JS_BUILD[@]}"
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
