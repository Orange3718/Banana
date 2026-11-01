#!/usr/bin/env python3
"""Make the daily Guardian report the focused affiliate loop and unknown metrics."""

import json
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "n8n/workflows/exports/AtemoyaOpsGuardian01.json"

QUERY = """WITH m AS (
 SELECT to_char((now() AT TIME ZONE 'Asia/Seoul')::date,'YYYY-MM-DD') AS review_date,
 (SELECT count(*) FROM execution_entity WHERE status='success' AND "startedAt">now()-interval '24 hours')::int AS n8n_success_24h,
 (SELECT count(*) FROM execution_entity WHERE status='error' AND "startedAt">now()-interval '24 hours')::int AS n8n_errors_24h,
 (SELECT count(*) FROM local_llm_runs WHERE status='complete' AND updated_at>now()-interval '24 hours')::int AS local_complete_24h,
 (SELECT count(*) FROM local_llm_runs WHERE status='error' AND updated_at>now()-interval '24 hours')::int AS local_errors_24h,
 COALESCE((SELECT extract(epoch FROM (now()-max(updated_at)))/60 FROM local_llm_runs WHERE status='complete'),99999)::int AS local_age_minutes,
 COALESCE((SELECT extract(epoch FROM (now()-max(collected_at)))/60 FROM source_observations),99999)::int AS source_age_minutes,
 (SELECT count(DISTINCT channel) FROM source_observations WHERE collected_at>now()-interval '24 hours')::int AS source_channels_24h,
 (SELECT count(*)-count(DISTINCT metadata->>'topic_key') FROM local_llm_runs WHERE status='complete' AND updated_at>now()-interval '24 hours' AND COALESCE(metadata->>'topic_key','')<>'')::int AS duplicate_topics_24h,
 COALESCE((SELECT healthy FROM affiliate_health_checks ORDER BY checked_at DESC LIMIT 1),false) AS affiliate_sample_healthy,
 COALESCE((SELECT extract(epoch FROM (now()-max(checked_at)))/60 FROM affiliate_health_checks),99999)::int AS affiliate_age_minutes,
 (SELECT count(*) FROM system_incidents WHERE state='open' AND severity='bad')::int AS open_bad,
 (SELECT count(*) FROM system_incidents WHERE state='open' AND severity='review')::int AS open_review,
 COALESCE((SELECT extract(epoch FROM (now()-max(checked_at)))/60 FROM system_health_checks),99999)::int AS watchdog_age_minutes,
 (SELECT count(*) FROM affiliate.jobs WHERE kind='direct_affiliate_publish')::int AS direct_total,
 (SELECT count(*) FROM affiliate.publications WHERE state='published' AND target='github_pages:Orange3718/Banana')::int AS direct_published,
 (SELECT count(*) FROM affiliate.jobs WHERE kind='direct_affiliate_publish' AND state IN ('queued','retry_wait') AND next_attempt_at<=now())::int AS direct_due,
 COALESCE((SELECT extract(epoch FROM (now()-min(next_attempt_at)))/60 FROM affiliate.jobs WHERE kind='direct_affiliate_publish' AND state IN ('queued','retry_wait') AND next_attempt_at<=now()),0)::int AS direct_oldest_due_minutes,
 (SELECT count(*) FROM affiliate.outbox WHERE kind='direct_affiliate_published' AND state='pending')::int AS outbox_pending,
 (SELECT count(*) FROM affiliate.outbox WHERE kind='direct_affiliate_published' AND state='failed')::int AS outbox_failed,
 COALESCE((SELECT extract(epoch FROM (now()-min(next_attempt_at)))/60 FROM affiliate.outbox WHERE kind='direct_affiliate_published' AND state='pending' AND next_attempt_at<=now()),0)::int AS outbox_oldest_pending_minutes,
 (SELECT count(*) FROM affiliate.import_batches)::int AS provider_batches,
 (SELECT count(*) FROM affiliate.cash_movements)::int AS cash_rows,
 (SELECT count(*) FROM revenue_channel_metrics)::int AS metric_rows
), j AS (
 SELECT m.*,
 CASE WHEN open_bad>0 OR watchdog_age_minutes>30 OR n8n_errors_24h>=3 OR source_age_minutes>180 OR local_errors_24h>0 OR (direct_due>0 AND direct_oldest_due_minutes>=45) OR outbox_failed>0 OR outbox_oldest_pending_minutes>=60 THEN 'BAD'
      WHEN open_review>0 OR n8n_errors_24h>0 OR source_channels_24h<2 OR NOT affiliate_sample_healthy OR affiliate_age_minutes>1560 OR local_age_minutes>180 OR duplicate_topics_24h>0 OR outbox_oldest_pending_minutes>=15 OR provider_batches=0 OR metric_rows=0 THEN 'REVIEW'
      ELSE 'GOOD' END AS status,
 CASE WHEN direct_due>0 AND direct_oldest_due_minutes>=45 THEN 'delayed' WHEN direct_total=direct_published AND direct_due=0 THEN 'idle' ELSE 'scheduled' END AS publication_state,
 CASE WHEN provider_batches=0 OR metric_rows=0 THEN 'unknown' ELSE 'rows_present' END AS measurement_state
 FROM m
)
SELECT j.*,jsonb_build_object(
 'n8n_success_24h',n8n_success_24h,'n8n_errors_24h',n8n_errors_24h,
 'local_complete_24h',local_complete_24h,'local_errors_24h',local_errors_24h,
 'local_age_minutes',local_age_minutes,'source_age_minutes',source_age_minutes,
 'source_channels_24h',source_channels_24h,'duplicate_topics_24h',duplicate_topics_24h,
 'affiliate_sample_healthy',affiliate_sample_healthy,'affiliate_age_minutes',affiliate_age_minutes,
 'open_bad',open_bad,'open_review',open_review,'watchdog_age_minutes',watchdog_age_minutes,
 'direct_total',direct_total,'direct_published',direct_published,'direct_due',direct_due,
 'direct_oldest_due_minutes',direct_oldest_due_minutes,'publication_state',publication_state,
 'outbox_pending',outbox_pending,'outbox_failed',outbox_failed,
 'provider_batches',provider_batches,'cash_rows',cash_rows,'metric_rows',metric_rows,
 'measurement_state',measurement_state,'owner_reported_revenue_krw',0,
 'owner_reported_as_of','2026-11-01') AS metrics FROM j;"""

FORMAT = r"""const m=$input.first().json;
const lines=[
  `인프라: Watchdog ${m.watchdog_age_minutes}분 전 · n8n 오류 ${m.n8n_errors_24h}건/24시간 · 열린 BAD ${m.open_bad}건`,
  `게시: 기존 직접 게시 ${m.direct_published}/${m.direct_total}건 · 상태 ${m.publication_state} · 기한초과 ${m.direct_due}건`,
  `알림: 미전달 ${m.outbox_pending}건 · 실패 ${m.outbox_failed}건`,
  `성과: 2026-11-01 사용자 보고 매출 0원 · 공급자 보고서 ${m.provider_batches}건 · 현금 기록 ${m.cash_rows}건 · 유입 지표 ${m.metric_rows}건 · 계측 ${m.measurement_state}`,
  '다음: GA4 실수신과 쿠팡 보고서 원본을 연결해 기존 게시물 한 묶음의 성과를 판단'
];
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const summary=lines.map(esc).join('\n');
const icon=m.status==='GOOD'?'✅':m.status==='BAD'?'🚨':'⚠️';
return [{json:{review_date:m.review_date,status:m.status,metrics:m.metrics,provider:'rule',model:'none',summary,telegram_text:(icon+' Atemoya 일일 운영 점검 | '+m.review_date+'\n판정: '+m.status+'\n\n'+summary).slice(0,3900)}}];"""


def main():
    payload = json.loads(PATH.read_text())
    workflow = payload[0] if isinstance(payload, list) else payload
    nodes = {node["name"]: node for node in workflow["nodes"]}
    assert workflow["id"] == "AtemoyaOpsGuardian01"
    assert "운영 지표 조회" in nodes and "요약 검증과 보고 작성" in nodes
    if "affiliate_sample_healthy" in nodes["운영 지표 조회"]["parameters"]["query"]:
        print("Guardian already focused")
        return
    assert "autopilot_actionable" in nodes["운영 지표 조회"]["parameters"]["query"]
    nodes["운영 지표 조회"]["parameters"]["query"] = QUERY
    nodes["요약 검증과 보고 작성"]["parameters"]["jsCode"] = FORMAT
    removed = {"규칙 판정과 로컬 요약 준비", "로컬 Qwen 운영 요약"}
    workflow["nodes"] = [node for node in workflow["nodes"] if node["name"] not in removed]
    for name in removed:
        workflow["connections"].pop(name, None)
    workflow["connections"]["운영 지표 조회"] = {"main": [[{"node": "요약 검증과 보고 작성", "type": "main", "index": 0}]]}
    PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Guardian focused affiliate report written")


if __name__ == "__main__":
    main()
