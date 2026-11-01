#!/usr/bin/env python3
"""Add deterministic read-only Telegram answers before the slow local model."""

import json
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "n8n/workflows/exports/AtemoyaTelegramMemory01.json"
SOURCE = "자연어 운영 문맥 조회"
FAST = "읽기 전용 즉답 작성"
BRANCH = "즉답 가능한 질문인가?"
MODEL = "로컬 Qwen 자연어 대화"
MEMORY = "자연어 대화 기억 저장"

SUMMARY_SQL = """COALESCE((SELECT json_build_object(
  'publications_total',(SELECT count(*) FROM affiliate.publications),
  'publications_published',(SELECT count(*) FROM affiliate.publications WHERE state='published'),
  'site_published',(SELECT count(*) FROM affiliate.publications WHERE state='published' AND target='github_pages:Orange3718/Banana'),
  'naver_published',(SELECT count(*) FROM affiliate.publications WHERE state='published' AND target LIKE 'naver_blog:%'),
  'outbox_pending',(SELECT count(*) FROM affiliate.outbox WHERE state='pending'),
  'click_rows',(SELECT count(*) FROM affiliate.click_events),
  'provider_batches',(SELECT count(*) FROM affiliate.import_batches),
  'journal_rows',(SELECT count(*) FROM affiliate.journal_entries),
  'cash_rows',(SELECT count(*) FROM affiliate.cash_movements),
  'metric_rows',(SELECT count(*) FROM revenue_channel_metrics))::text),'{}') AS affiliate_summary_context"""

FAST_CODE = r"""const ctx=$input.first().json;
const text=String(ctx.user_text||'').trim();
const cleaned=text.replace(/^\//,'');
let status={}, affiliate={};
try { status=JSON.parse(String(ctx.db_status_context||'{}')); } catch(e) {}
try { affiliate=JSON.parse(String(ctx.affiliate_summary_context||'{}')); } catch(e) {}
const n=v=>Number(v||0);
let response='';
let intent='chat';
if (/^(?:오늘\s*)?(?:운영\s*|시스템\s*)?상태(?:\s*(?:어때|알려줘|보고|확인|요약))?\??$/i.test(cleaned)) {
  intent='status';
  response=`현재 n8n 활성 워크플로 ${n(status.active_workflows)}개, 최근 24시간 n8n 오류 ${n(status.n8n_errors_24h)}건, 열린 사건 ${n(status.open_incidents)}건입니다. 제휴 게시 총 ${n(affiliate.publications_published)}건(사이트 ${n(affiliate.site_published)}건·네이버 ${n(affiliate.naver_published)}건)이며 미전달 알림 ${n(affiliate.outbox_pending)}건입니다. 2026-11-01 사용자 보고 매출은 0원이고 공급자 보고서 ${n(affiliate.provider_batches)}건·현금 기록 ${n(affiliate.cash_rows)}건이라 성과 계측은 아직 미완료입니다.`;
} else if (/(?:매출|수익|돈\s*벌|성과)/i.test(cleaned) && !/(?:승인|게시해|올려|공개해)/i.test(cleaned)) {
  intent='revenue';
  response=`2026-11-01 사용자 보고 매출은 0원입니다. DB에는 제휴 클릭 ${n(affiliate.click_rows)}건, 공급자 보고서 ${n(affiliate.provider_batches)}건, 수익 원장 ${n(affiliate.journal_rows)}건, 현금 입금 ${n(affiliate.cash_rows)}건, 유입 지표 ${n(affiliate.metric_rows)}건이 있습니다. 데이터가 없는 항목은 실제 0으로 확정하지 않습니다.`;
} else if (/(?:최근\s*게시|게시\s*링크|공개\s*글)/i.test(cleaned) && !/(?:게시해|올려|공개해)/i.test(cleaned)) {
  intent='publications';
  response=`최근 공개 링크:\n${String(ctx.publications||'기록 없음').slice(0,2500)}`;
} else if (/(?:승인\s*대기|결정\s*대기|대기\s*승인)/i.test(cleaned)) {
  intent='approvals';
  response=`현재 대기 중인 승인 안건은 ${n(ctx.pending_count)}건입니다.${n(ctx.pending_count)?'\n'+String(ctx.approval_context||'').slice(0,1800):''}`;
}
return [{json:{...ctx,response_text:response,provider:response?'rule':'',model:response?'none':'',model_intent:intent,should_decide:false}}];"""


def main():
    payload = json.loads(PATH.read_text())
    workflow = payload[0] if isinstance(payload, list) else payload
    nodes = {node["name"]: node for node in workflow["nodes"]}
    if FAST in nodes:
        query = nodes[SOURCE]["parameters"]["query"]
        if "'site_published'" not in query:
            old = "'publications_published',(SELECT count(*) FROM affiliate.publications WHERE state='published'),"
            new = old + "\n  'site_published',(SELECT count(*) FROM affiliate.publications WHERE state='published' AND target='github_pages:Orange3718/Banana'),\n  'naver_published',(SELECT count(*) FROM affiliate.publications WHERE state='published' AND target LIKE 'naver_blog:%'),"
            assert old in query
            nodes[SOURCE]["parameters"]["query"] = query.replace(old, new)
        nodes[FAST]["parameters"]["jsCode"] = FAST_CODE
        PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        print("Telegram fast status: updated")
        return
    query = nodes[SOURCE]["parameters"]["query"]
    marker = " AS db_revenue_context;"
    assert marker in query
    nodes[SOURCE]["parameters"]["query"] = query.replace(marker, " AS db_revenue_context,\n" + SUMMARY_SQL + ";")
    memory_query = nodes[MEMORY]["parameters"]["query"]
    old = "VALUES($2,$6,'telegram_natural',NULL,'ollama-local','qwen3.5:4b',$8,"
    assert old in memory_query
    nodes[MEMORY]["parameters"]["query"] = memory_query.replace(old, "VALUES($2,$6,'telegram_natural',NULL,$9,$10,$8,")
    replacement = nodes[MEMORY]["parameters"]["options"]["queryReplacement"]
    assert replacement.endswith("$json.response_text] }}")
    nodes[MEMORY]["parameters"]["options"]["queryReplacement"] = replacement.replace("$json.response_text] }}", "$json.response_text,$json.provider||'ollama-local',$json.model||'qwen3.5:4b'] }}")
    workflow["nodes"].extend([
        {"parameters": {"jsCode": FAST_CODE}, "id": "telegram-fast-status-01", "name": FAST,
         "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1370, 900]},
        {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
             "conditions": [{"id": "telegram-fast-status-condition", "leftValue": "={{ Boolean($json.response_text) }}", "rightValue": True,
                 "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}},
         "id": "telegram-fast-status-if-01", "name": BRANCH, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1590, 900]},
    ])
    workflow["connections"][SOURCE] = {"main": [[{"node": FAST, "type": "main", "index": 0}]]}
    workflow["connections"][FAST] = {"main": [[{"node": BRANCH, "type": "main", "index": 0}]]}
    workflow["connections"][BRANCH] = {"main": [
        [{"node": MEMORY, "type": "main", "index": 0}],
        [{"node": MODEL, "type": "main", "index": 0}],
    ]}
    PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Telegram fast status: added")


if __name__ == "__main__":
    main()
