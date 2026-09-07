#!/usr/bin/env bash
cd "$(dirname "$0")"
bash tools/start_neural.sh
PORT="$(grep -E '^NEURAL_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2)"
open "http://127.0.0.1:${PORT:-8765}"
