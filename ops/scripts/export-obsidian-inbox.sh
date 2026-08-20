#!/usr/bin/env bash
set -euo pipefail

vault_root="${ATEMOYA_OBSIDIAN_VAULT:-$HOME/AtemoyaVault}"
docker_bin="${ATEMOYA_DOCKER_BIN:-/usr/local/bin/docker}"
inbox_dir="$vault_root/00 Inbox"
output="$inbox_dir/Atemoya Inbox.md"
temporary="$(mktemp "$inbox_dir/.atemoya-inbox.XXXXXX")"
trap 'rm -f "$temporary"' EXIT

query() {
  "$docker_bin" exec atemoya-postgres sh -lc \
    "psql -X -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -F ' | ' -c \"$1\""
}

ideas="$(query "select '- ' || coalesce(title,'(untitled)') || ' | status: ' || status || coalesce(' | score: ' || score::text,'') from business_ideas where status in ('new','evaluating') order by discovered_at desc limit 30")"
approvals="$(query "select '- ' || coalesce(approval_key,'approval #' || id::text) || ' | via: ' || requested_via || ' | requested: ' || to_char(requested_at at time zone 'Asia/Seoul','YYYY-MM-DD HH24:MI') from approvals where status='pending' order by requested_at desc limit 30")"
failures="$(query "select '- ' || workflow_key || ' | ' || status || ' | ' || to_char(started_at at time zone 'Asia/Seoul','YYYY-MM-DD HH24:MI') || coalesce(' | ' || left(replace(error_summary,E'\\n',' '),160),'') from executions where status in ('failed','retrying') and started_at >= now() - interval '7 days' order by started_at desc limit 30")"

{
  echo "# Atemoya Inbox"
  echo
  echo "> PostgreSQL에서 자동 생성된 검토용 요약입니다. 원본 운영 기록은 PostgreSQL입니다."
  echo
  echo "마지막 수집: $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"
  echo
  echo "## 새 사업 아이디어"
  echo
  if [[ -n "$ideas" ]]; then printf '%s\n' "$ideas"; else echo "- 없음"; fi
  echo
  echo "## 승인 대기"
  echo
  if [[ -n "$approvals" ]]; then printf '%s\n' "$approvals"; else echo "- 없음"; fi
  echo
  echo "## 최근 7일 실패 및 재시도"
  echo
  if [[ -n "$failures" ]]; then printf '%s\n' "$failures"; else echo "- 없음"; fi
} > "$temporary"

chmod 600 "$temporary"
mv "$temporary" "$output"
trap - EXIT
echo "$output"
