#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
USER_DOMAIN="gui/$(id -u)"

mkdir -p "$AGENT_DIR" "$ROOT/next_data/logs"

write_agent() {
  local label="$1"
  local service="$2"
  local stdout="$3"
  local stderr="$4"
  local plist="$AGENT_DIR/${label}.plist"

  tee "$plist" >/dev/null <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${ROOT}/tools/run_neural_service.sh</string>
    <string>${service}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${ROOT}/next_data/logs/${stdout}</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/next_data/logs/${stderr}</string>
</dict>
</plist>
EOF

  plutil -lint "$plist" >/dev/null
  launchctl bootout "$USER_DOMAIN" "$plist" 2>/dev/null || true
  launchctl bootstrap "$USER_DOMAIN" "$plist"
  echo "Installed ${label}"
}

chmod +x "$ROOT/tools/run_neural_service.sh"

write_agent com.orange3718.upbit-auto-trader.api api \
  launchd-api.out.log launchd-api.err.log
write_agent com.orange3718.upbit-auto-trader.upbit-collector upbit-collector \
  launchd-upbit-collector.out.log launchd-upbit-collector.err.log
write_agent com.orange3718.upbit-auto-trader.binance-futures-collector binance-futures-collector \
  launchd-binance-futures-collector.out.log launchd-binance-futures-collector.err.log

echo "LaunchAgents installed. Check: launchctl print ${USER_DOMAIN}/com.orange3718.upbit-auto-trader.api"
