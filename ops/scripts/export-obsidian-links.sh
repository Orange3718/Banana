#!/usr/bin/env bash
# Renders vault_links (found by the AtemoyaVaultLinker01 n8n workflow) into a
# single human-readable Markdown note. This is a summary list, not a true
# Obsidian wikilink graph yet: source_observations/local_llm_runs don't have
# individual per-item notes in the vault, so there is nothing for [[...]] to
# point at. Phase 2 (not built yet) would generate one note per linked item
# so Obsidian's graph view could show real connections.
set -euo pipefail

vault_root="${ATEMOYA_OBSIDIAN_VAULT:-$HOME/AtemoyaVault}"
docker_bin="${ATEMOYA_DOCKER_BIN:-/usr/local/bin/docker}"
ops_dir="$vault_root/10 Operations"
output="$ops_dir/Atemoya Connections.md"
temporary="$(mktemp "$ops_dir/.atemoya-connections.XXXXXX")"
trap 'rm -f "$temporary"' EXIT

query() {
  "$docker_bin" exec atemoya-postgres sh -lc \
    "psql -X -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -F ' | ' -c \"$1\""
}

links="$(query "select '- **' || vl.relation || '**: ' || coalesce(so1.item_title, llr1.task_name, vl.from_type || '#' || vl.from_id) || '  <->  ' || coalesce(so2.item_title, llr2.task_name, vl.to_type || '#' || vl.to_id) || ' — ' || vl.reason from vault_links vl left join source_observations so1 on vl.from_type='source_observation' and so1.id::text=vl.from_id left join local_llm_runs llr1 on vl.from_type='local_llm_run' and llr1.run_key::text=vl.from_id left join source_observations so2 on vl.to_type='source_observation' and so2.id::text=vl.to_id left join local_llm_runs llr2 on vl.to_type='local_llm_run' and llr2.run_key::text=vl.to_id order by vl.created_at desc limit 100")"

{
  echo "# Atemoya Connections"
  echo
  echo "> \`vault_links\` 테이블에서 자동 생성됨 (AtemoyaVaultLinker01, 로컬 Qwen 판단)."
  echo "> 아직 개별 노트 단위 [[위키링크]]는 아니고, 관련성 목록입니다."
  echo
  echo "마지막 수집: $(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"
  echo
  echo "## 최근 발견된 연관관계"
  echo
  if [[ -n "$links" ]]; then printf '%s\n' "$links"; else echo "- 아직 없음 (AtemoyaVaultLinker01이 아직 비활성 상태이거나 최근 실행에서 관련 쌍을 찾지 못했습니다)"; fi
} > "$temporary"

chmod 600 "$temporary"
mv "$temporary" "$output"
trap - EXIT
echo "$output"
