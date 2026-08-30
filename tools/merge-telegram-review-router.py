#!/usr/bin/env python3
"""Merge local-result review commands into the single Telegram inbound router."""
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "n8n" / "workflows" / "exports"
MEMORY_PATH = EXPORTS / "AtemoyaTelegramMemory01.json"
REVIEW_PATH = EXPORTS / "AtemoyaLocalLLMReviewGate01.json"


def load_one(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, payload[0] if isinstance(payload, list) else payload


def main():
    memory_payload, memory = load_one(MEMORY_PATH)
    review_payload, review = load_one(REVIEW_PATH)
    review_payload[0]["active"] = False

    names = {node["name"] for node in memory["nodes"]}
    approval_query = (
        "WITH p AS (SELECT $1::bigint AS chat_id, $2::bigint AS decision_id, $3::text AS new_status, $4::text AS note), "
        "updated AS (UPDATE approval_requests a SET status=p.new_status, decided_at=NOW(), decision_note=NULLIF(p.note,'') FROM p "
        "WHERE a.id=p.decision_id AND a.status='pending' AND p.new_status IN ('approved','deferred','rejected') "
        "RETURNING a.id,a.title,a.status,a.decision_note), "
        "existing AS (SELECT a.id,a.title,a.status,a.decision_note FROM approval_requests a,p WHERE a.id=p.decision_id) "
        "SELECT p.chat_id, CASE "
        "WHEN p.decision_id IS NULL OR p.new_status='invalid' THEN '명령 형식이 맞지 않습니다. 예: /승인 3 게시' "
        "WHEN u.id IS NOT NULL AND u.status='approved' THEN '✅ 승인 완료 #'||u.id||' · '||u.title||COALESCE(' · 선택: '||u.decision_note,'') "
        "WHEN u.id IS NOT NULL AND u.status='deferred' THEN '⏸ 보류 완료 #'||u.id||' · '||u.title "
        "WHEN u.id IS NOT NULL AND u.status='rejected' THEN '❌ 거절 완료 #'||u.id||' · '||u.title||COALESCE(' · 사유: '||u.decision_note,'') "
        "WHEN e.status='approved' THEN '✅ 이미 승인 완료 #'||e.id||' · '||e.title "
        "WHEN e.status='deferred' THEN '⏸ 이미 보류 완료 #'||e.id||' · '||e.title "
        "WHEN e.status='rejected' THEN '❌ 이미 거절 완료 #'||e.id||' · '||e.title "
        "ELSE '존재하지 않는 결정번호입니다: '||p.decision_id END AS response_text "
        "FROM p LEFT JOIN updated u ON TRUE LEFT JOIN existing e ON TRUE;"
    )
    for node in memory["nodes"]:
        if node["name"] == "승인 상태 저장":
            node["parameters"]["query"] = approval_query

    review_names = ["GOOD BAD 수정 해석", "검토 결과 PostgreSQL 저장", "검토 결과 답장"]
    for node in review["nodes"]:
        if node["name"] in review_names and node["name"] not in names:
            memory["nodes"].append(deepcopy(node))

    gate_name = "로컬 검토 명령인가?"
    if gate_name not in names:
        memory["nodes"].append({
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": "local-review-command-condition",
                        "leftValue": "={{ /^(?:\\/)?(?:GOOD|BAD)(?:\\s+.+)?$|^수정\\s*:/i.test($json.message.text || '') }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": "local-review-router-01",
            "name": gate_name,
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [720, 300],
        })

    memory["connections"]["사업 승인 명령인가?"]["main"][1] = [
        {"node": gate_name, "type": "main", "index": 0}
    ]
    memory["connections"][gate_name] = {"main": [
        [{"node": "GOOD BAD 수정 해석", "type": "main", "index": 0}],
        [{"node": "기억 조회 명령인가?", "type": "main", "index": 0}],
    ]}
    memory["connections"]["GOOD BAD 수정 해석"] = {"main": [[
        {"node": "검토 결과 PostgreSQL 저장", "type": "main", "index": 0}
    ]]}
    memory["connections"]["검토 결과 PostgreSQL 저장"] = {"main": [[
        {"node": "검토 결과 답장", "type": "main", "index": 0}
    ]]}

    MEMORY_PATH.write_text(json.dumps(memory_payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    REVIEW_PATH.write_text(json.dumps(review_payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
