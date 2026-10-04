#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
runtime_root="/Users/orange/Atemoya/runtime"
public_worktree="$runtime_root/banana-public"
uid="$(id -u)"
label="com.atemoya.affiliate-direct-publisher"
agent_source="$repo_root/ops/launchd/$label.plist"
agent_target="$HOME/Library/LaunchAgents/$label.plist"
dashboard_label="com.atemoya.local-llm-status"
dashboard_target="$HOME/Library/LaunchAgents/$dashboard_label.plist"

test "$(git -C "$repo_root" branch --show-current)" != "main" || {
  echo "Refusing to install an unreviewed publisher from main." >&2
  exit 1
}

"$repo_root/ops/scripts/backup.sh"
"$repo_root/ops/scripts/apply-migrations.sh"
PYTHONPATH="$repo_root/tools" /usr/bin/python3 "$repo_root/tools/affiliate_direct_publisher.py" --validate-all >/dev/null
PYTHONPATH="$repo_root/tools" /usr/bin/python3 "$repo_root/tools/seed_affiliate_publication_batch.py" --apply >/dev/null

mkdir -p "$runtime_root"
if [[ ! -e "$public_worktree/.git" ]]; then
  git -C "$repo_root" fetch origin main
  git -C "$repo_root" worktree add --detach "$public_worktree" origin/main
fi
test -z "$(git -C "$public_worktree" status --porcelain)" || {
  echo "Publication worktree is not clean: $public_worktree" >&2
  exit 1
}

install -m 0644 "$agent_source" "$agent_target"
install -m 0644 "$repo_root/ops/launchd/$dashboard_label.plist" "$dashboard_target"
launchctl bootout "gui/$uid/$label" 2>/dev/null || true
for _ in 1 2 3; do
  launchctl print "gui/$uid/$label" >/dev/null 2>&1 || break
  sleep 1
done
launchctl bootstrap "gui/$uid" "$agent_target"

# The legacy workflow makes generic news drafts and asks for approval. It is
# deliberately unpublished; the direct queue below is its replacement for
# Coupang publishing, not an implicit approval of stale legacy candidates.
docker exec atemoya-n8n n8n unpublish:workflow --id=AtemoyaRevenueAutopilot01 >/dev/null 2>&1 || true

if launchctl print "gui/$uid/$dashboard_label" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$uid/$dashboard_label"
else
  launchctl bootstrap "gui/$uid" "$dashboard_target"
fi
"$repo_root/ops/scripts/verify.sh"
echo "Direct affiliate publisher installation: PASS"
