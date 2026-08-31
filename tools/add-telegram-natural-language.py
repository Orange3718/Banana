#!/usr/bin/env python3
"""Add a local-LLM natural-language path to Atemoya's Telegram router."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "n8n" / "workflows" / "exports"


def load(name):
    path = EXPORTS / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    return path, payload, payload[0] if isinstance(payload, list) else payload


def save(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def upsert_node(workflow, node):
    for index, existing in enumerate(workflow["nodes"]):
        if existing["name"] == node["name"]:
            workflow["nodes"][index] = node
            return
    workflow["nodes"].append(node)


def telegram_router():
    path, payload, workflow = load("AtemoyaTelegramMemory01.json")

    context_query = """SELECT
$1::bigint AS chat_id,$2::bigint AS update_id,$3::bigint AS message_id,
$4::bigint AS user_id,$5::text AS username,$6::text AS user_text,$7::jsonb AS raw_update,
COALESCE((SELECT string_agg('사용자: '||x.message_text||COALESCE(E'\\nAtemoya: '||NULLIF(x.raw_update->>'assistant_reply',''),''),E'\\n' ORDER BY x.received_at) FROM (SELECT message_text,raw_update,received_at FROM telegram_memory WHERE chat_id=$1::bigint ORDER BY received_at DESC LIMIT 8) x),'대화 기록 없음') AS memory_context,
COALESCE((SELECT string_agg('#'||id||' ['||status||'] '||title,E'\\n' ORDER BY requested_at DESC) FROM (SELECT id,status,title,requested_at FROM approval_requests ORDER BY requested_at DESC LIMIT 5) a),'승인 안건 없음') AS approval_context,
(SELECT count(*)::int FROM approval_requests WHERE status='pending') AS pending_count,
(SELECT id FROM approval_requests WHERE status='pending' ORDER BY requested_at DESC LIMIT 1) AS latest_pending_id,
COALESCE((SELECT string_agg(stage||' '||count,E', ' ORDER BY stage) FROM (SELECT stage,count(*)::text AS count FROM revenue_autopilot_jobs GROUP BY stage) j),'수익 작업 없음') AS revenue_jobs,
COALESCE((SELECT string_agg(task_name||' ['||status||'] '||left(COALESCE(result_summary,''),180),E'\\n' ORDER BY updated_at DESC) FROM (SELECT task_name,status,result_summary,updated_at FROM local_llm_runs ORDER BY updated_at DESC LIMIT 4) r),'로컬 추론 기록 없음') AS local_runs,
COALESCE((SELECT string_agg(title||' — '||published_url,E'\\n' ORDER BY published_at DESC) FROM (SELECT title,published_url,published_at FROM content WHERE published_url IS NOT NULL ORDER BY published_at DESC LIMIT 3) c),'최근 공개 콘텐츠 없음') AS publications;"""

    system_prompt = """당신은 Atemoya 운영 대화 비서다. 한국어 존댓말로 자연스럽고 짧게 답한다.
사용자는 명령어를 외울 필요가 없다. 제공된 PostgreSQL 운영 문맥만 사실로 사용하고 없는 사실은 만들지 않는다.
승인·게시·보류·거절 의도는 이해하되 실제 변경은 후속 결정 규칙이 검증한다.
비밀번호, API 키, 2FA, 개인키를 요구하거나 출력하지 않는다.
반드시 JSON 하나만 출력한다: {\"intent\":\"chat|status|approve|defer|reject|remember\",\"decision_id\":null,\"note\":\"\",\"reply\":\"사용자에게 보낼 한국어 답변\"}.
승인 번호가 문장에 분명히 있으면 decision_id에 숫자를 넣고, 불분명하면 null이다."""

    context_node = {
        "parameters": {"operation": "executeQuery", "query": context_query, "options": {"queryReplacement": "={{ [$json.message.chat.id,$json.update_id,$json.message.message_id,$json.message.from.id,($json.message.from.username||''),($json.message.text||$json.message.caption||''),JSON.stringify($json)] }}"}},
        "id": "telegram-natural-context-01", "name": "자연어 운영 문맥 조회", "type": "n8n-nodes-base.postgres", "typeVersion": 2.6, "position": [1220, 760],
        "credentials": {"postgres": {"id": "AtemoyaPostgresMemory01", "name": "Atemoya PostgreSQL Memory"}},
    }
    llm_node = {
        "parameters": {"method": "POST", "url": "http://host.docker.internal:11434/api/chat", "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
            "body": "={{ JSON.stringify({model:'qwen3.5:4b',stream:false,think:false,format:'json',options:{num_predict:700,temperature:0.2},messages:[{role:'system',content:" + json.dumps(system_prompt, ensure_ascii=False) + "},{role:'user',content:'[사용자 입력]\\n'+$json.user_text+'\\n\\n[최근 대화]\\n'+$json.memory_context+'\\n\\n[승인 안건]\\n'+$json.approval_context+'\\n\\n[수익 작업]\\n'+$json.revenue_jobs+'\\n\\n[최근 로컬 추론]\\n'+$json.local_runs+'\\n\\n[최근 공개]\\n'+$json.publications}]}) }}",
            "options": {"timeout": 180000}},
        "id": "telegram-natural-ollama-01", "name": "로컬 Qwen 자연어 대화", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1460, 760],
        "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 3000, "onError": "continueRegularOutput",
    }
    validate_code = r"""const ctx=$('자연어 운영 문맥 조회').item.json;
const text=String(ctx.user_text||'').trim();
let model={};
try { model=JSON.parse(String($json?.message?.content||'').replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'').trim()); } catch(e) {}
const idMatch=text.match(/(?:결정\s*번호|번호|#)\s*(\d+)/i)||text.match(/^\s*(\d+)\s*(?:번)?\s*(?:승인|게시|보류|거절)/i);
const explicitId=idMatch?Number(idMatch[1]):null;
const approve=/(승인|게시해|게시하자|올려줘|올려|공개해|진행해|좋아.{0,8}게시)/i.test(text);
const defer=/(보류|나중에|잠깐\s*멈춰|일단\s*멈춰)/i.test(text);
const reject=/(거절|게시하지\s*마|하지\s*마|취소해)/i.test(text);
let status=approve?'approved':defer?'deferred':reject?'rejected':'';
let decisionId=explicitId;
if(status&&!decisionId&&Number(ctx.pending_count)===1) decisionId=Number(ctx.latest_pending_id);
let response=String(model.reply||'').trim();
if(status&&!decisionId){
  response=Number(ctx.pending_count)>1?'대기 중인 승인 안건이 여러 개입니다. “결정번호 7 게시해”처럼 번호와 함께 말씀해 주세요.':'현재 처리할 대기 승인 안건이 없습니다.';
  status='';
}
if(!response) response='말씀하신 내용을 확인했습니다. 현재 운영 기록을 기준으로 다시 질문해 주세요.';
return [{json:{...ctx,status,decision_id:decisionId,note:String(model.note||''),response_text:response,should_decide:Boolean(status&&decisionId),model_intent:String(model.intent||'chat'),provider:'ollama-local',model:'qwen3.5:4b'}}];"""
    validate_node = {"parameters": {"jsCode": validate_code}, "id": "telegram-natural-validate-01", "name": "자연어 의도 안전 검증", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [1700, 760]}
    decision_if = {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"id": "natural-decision-condition", "leftValue": "={{ $json.should_decide }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, "id": "telegram-natural-decision-if-01", "name": "자연어 결정인가?", "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [1940, 760]}

    decision_query = """WITH p AS (SELECT $1::bigint chat_id,$2::bigint decision_id,$3::text new_status,$4::text note),
updated AS (UPDATE approval_requests a SET status=p.new_status,decided_at=NOW(),decision_note=NULLIF(p.note,'') FROM p WHERE a.id=p.decision_id AND a.status='pending' AND p.new_status IN ('approved','deferred','rejected') RETURNING a.id,a.title,a.status),
synced AS (UPDATE revenue_autopilot_jobs j SET stage=CASE WHEN u.status='approved' THEN 'approved' ELSE 'rejected' END,updated_at=NOW(),finished_at=CASE WHEN u.status='approved' THEN j.finished_at ELSE NOW() END FROM updated u WHERE j.approval_request_id=u.id AND j.stage='awaiting_approval' RETURNING j.id),
existing AS (SELECT a.id,a.title,a.status FROM approval_requests a,p WHERE a.id=p.decision_id)
SELECT p.chat_id,CASE WHEN u.status='approved' THEN '좋습니다. #'||u.id||' 게시를 승인했고 자동 게시 대기열에 전달했습니다.' WHEN u.status='deferred' THEN '#'||u.id||' 안건을 보류했습니다.' WHEN u.status='rejected' THEN '#'||u.id||' 안건을 거절했습니다.' WHEN e.id IS NULL THEN '해당 결정번호를 찾지 못했습니다.' ELSE '#'||e.id||' 안건은 이미 '||e.status||' 상태입니다.' END response_text FROM p LEFT JOIN updated u ON TRUE LEFT JOIN existing e ON TRUE;"""
    decision_node = {"parameters": {"operation": "executeQuery", "query": decision_query, "options": {"queryReplacement": "={{ [$json.chat_id,$json.decision_id,$json.status,$json.note] }}"}}, "id": "telegram-natural-decision-save-01", "name": "자연어 결정 저장", "type": "n8n-nodes-base.postgres", "typeVersion": 2.6, "position": [2180, 660], "credentials": {"postgres": {"id": "AtemoyaPostgresMemory01", "name": "Atemoya PostgreSQL Memory"}}}
    decision_reply = {"parameters": {"chatId": "={{ $json.chat_id }}", "text": "={{ $json.response_text }}", "additionalFields": {"disable_web_page_preview": True, "appendAttribution": False}}, "id": "telegram-natural-decision-reply-01", "name": "자연어 결정 답장", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2, "position": [2420, 660], "credentials": {"telegramApi": {"id": "6WaLMIqUth2LtuDZ", "name": "Telegram account"}}}

    memory_query = """INSERT INTO telegram_memory(update_id,chat_id,message_id,user_id,username,message_text,raw_update)
VALUES($1,$2,$3,$4,$5,$6,jsonb_set($7::jsonb,'{assistant_reply}',to_jsonb($8::text),true))
ON CONFLICT(update_id) DO UPDATE SET message_text=EXCLUDED.message_text,raw_update=EXCLUDED.raw_update
RETURNING chat_id,$8::text AS response_text;"""
    memory_node = {"parameters": {"operation": "executeQuery", "query": memory_query, "options": {"queryReplacement": "={{ [$json.update_id,$json.chat_id,$json.message_id,$json.user_id,$json.username,$json.user_text,JSON.stringify($json.raw_update),$json.response_text] }}"}}, "id": "telegram-natural-memory-01", "name": "자연어 대화 기억 저장", "type": "n8n-nodes-base.postgres", "typeVersion": 2.6, "position": [2180, 860], "credentials": {"postgres": {"id": "AtemoyaPostgresMemory01", "name": "Atemoya PostgreSQL Memory"}}}
    chat_reply = {"parameters": {"chatId": "={{ $json.chat_id }}", "text": "={{ $json.response_text }}", "additionalFields": {"disable_web_page_preview": True, "appendAttribution": False}}, "id": "telegram-natural-chat-reply-01", "name": "자연어 대화 답장", "type": "n8n-nodes-base.telegram", "typeVersion": 1.2, "position": [2420, 860], "credentials": {"telegramApi": {"id": "6WaLMIqUth2LtuDZ", "name": "Telegram account"}}}

    for node in (context_node, llm_node, validate_node, decision_if, decision_node, decision_reply, memory_node, chat_reply):
        upsert_node(workflow, node)
    workflow["connections"]["AI 질문인가?"]["main"][1] = [{"node": "자연어 운영 문맥 조회", "type": "main", "index": 0}]
    workflow["connections"]["자연어 운영 문맥 조회"] = {"main": [[{"node": "로컬 Qwen 자연어 대화", "type": "main", "index": 0}]]}
    workflow["connections"]["로컬 Qwen 자연어 대화"] = {"main": [[{"node": "자연어 의도 안전 검증", "type": "main", "index": 0}]]}
    workflow["connections"]["자연어 의도 안전 검증"] = {"main": [[{"node": "자연어 결정인가?", "type": "main", "index": 0}]]}
    workflow["connections"]["자연어 결정인가?"] = {"main": [[{"node": "자연어 결정 저장", "type": "main", "index": 0}], [{"node": "자연어 대화 기억 저장", "type": "main", "index": 0}]]}
    workflow["connections"]["자연어 결정 저장"] = {"main": [[{"node": "자연어 결정 답장", "type": "main", "index": 0}]]}
    workflow["connections"]["자연어 대화 기억 저장"] = {"main": [[{"node": "자연어 대화 답장", "type": "main", "index": 0}]]}
    save(path, payload)


def revenue_guard():
    path, payload, workflow = load("AtemoyaRevenueAutopilot01.json")
    guard = {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"id": "claimed-job-condition", "leftValue": "={{ Number.isInteger(Number($json.job_id)) && Number($json.job_id) > 0 }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, "id": "revenue-claimed-job-if-01", "name": "처리 후보 있는가?", "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [700, 300]}
    upsert_node(workflow, guard)
    workflow["connections"]["후보 동기화와 1건 점유"] = {"main": [[{"node": "처리 후보 있는가?", "type": "main", "index": 0}]]}
    workflow["connections"]["처리 후보 있는가?"] = {"main": [[{"node": "근거 제한 장문 프롬프트", "type": "main", "index": 0}], []]}
    save(path, payload)


if __name__ == "__main__":
    telegram_router()
    revenue_guard()
