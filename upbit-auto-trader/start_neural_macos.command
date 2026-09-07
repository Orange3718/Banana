#!/usr/bin/env bash
cd "$(dirname "$0")"
bash tools/start_neural.sh
open http://127.0.0.1:8765
