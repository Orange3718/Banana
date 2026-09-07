#!/usr/bin/env python3
"""Answer Atemoya Telegram-style natural-language DB questions with local Ollama.

The model classifies and summarizes. SQL execution stays on a fixed whitelist
of read-only operational views.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


MODEL = "qwen3.5:4b"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DB_CMD = [
    "/usr/local/bin/docker",
    "exec",
    "atemoya-postgres",
    "psql",
    "-X",
    "-U",
    "n8n",
    "-d",
    "n8n",
    "-At",
]


SAFE_QUERIES = {
    "status": "SELECT row_to_json(x) FROM (SELECT * FROM v_atemoya_operational_status) x;",
    "failures": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_recent_failures LIMIT 8) x;",
    "approvals": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_pending_approvals LIMIT 8) x;",
    "publications": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_recent_publications LIMIT 8) x;",
    "local_llm": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_local_llm_status LIMIT 8) x;",
    "sources": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_source_freshness LIMIT 8) x;",
    "incidents": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_recent_incidents LIMIT 8) x;",
    "revenue": "SELECT COALESCE(json_agg(x), '[]'::json) FROM (SELECT * FROM v_atemoya_revenue_status) x;",
}


KEYWORDS = (
    ("failures", re.compile(r"오류|실패|에러|문제|원인|장애")),
    ("approvals", re.compile(r"승인|보류|거절|대기|안건")),
    ("publications", re.compile(r"게시|공개|링크|URL|콘텐츠")),
    ("local_llm", re.compile(r"로컬|모델|LLM|qwen|추론|ollama")),
    ("sources", re.compile(r"수집|소스|근거|뉴스|자료")),
    ("incidents", re.compile(r"인시던트|incident|복구|심각|경고")),
    ("revenue", re.compile(r"수익|매출|클릭|전환|성과|오토파일럿")),
)


@dataclass
class Answer:
    query_key: str
    response_text: str
    raw_model: dict[str, Any]


def db_scalar(sql: str) -> str:
    result = subprocess.run(DB_CMD + ["-c", sql], text=True, capture_output=True, check=True)
    return result.stdout.strip()


def db_exec(sql: str, values: tuple[str, ...]) -> None:
    escaped = []
    for value in values:
        escaped.append("'" + str(value).replace("'", "''") + "'")
    rendered = sql % tuple(escaped)
    subprocess.run(DB_CMD + ["-c", rendered], text=True, capture_output=True, check=True)


def ollama(messages: list[dict[str, str]], *, timeout: int = 90) -> dict[str, Any]:
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 500},
        "messages": messages,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = str(body.get("message", {}).get("content", "")).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"reply": content}
    parsed["_ollama_done"] = body.get("done")
    return parsed


def fallback_key(text: str) -> str:
    for key, pattern in KEYWORDS:
        if pattern.search(text):
            return key
    return "status"


def classify(text: str) -> dict[str, Any]:
    catalog = "\n".join(f"- {key}" for key in SAFE_QUERIES)
    system = (
        "Atemoya 텔레그램 운영 질의를 안전한 DB 조회 키로 분류한다. "
        "반드시 JSON 하나만 출력한다. 형식: "
        '{"query_key":"status|failures|approvals|publications|local_llm|sources|incidents|revenue","reason":""}. '
        "없는 정보는 만들지 않는다."
    )
    try:
        model = ollama(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"[허용 키]\n{catalog}\n\n[사용자 질문]\n{text}"},
            ],
            timeout=45,
        )
    except (urllib.error.URLError, TimeoutError, subprocess.SubprocessError):
        return {"query_key": fallback_key(text), "reason": "fallback"}
    key = str(model.get("query_key", "")).strip()
    if key not in SAFE_QUERIES:
        key = fallback_key(text)
    model["query_key"] = key
    return model


def summarize(text: str, query_key: str, rows: str) -> dict[str, Any]:
    system = (
        "당신은 Atemoya 운영 비서다. DB 조회 결과만 근거로 한국어 존댓말로 짧게 답한다. "
        "비밀값, 토큰, 개인키를 요구하거나 출력하지 않는다. "
        "반드시 JSON 하나만 출력한다. 형식: {\"reply\":\"\"}."
    )
    try:
        return ollama(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"[질문]\n{text}\n\n[조회 키]\n{query_key}\n\n[DB 결과]\n{rows[:7000]}"},
            ],
            timeout=90,
        )
    except (urllib.error.URLError, TimeoutError):
        return {"reply": deterministic_reply(query_key, rows)}


def deterministic_reply(query_key: str, rows: str) -> str:
    if not rows:
        return "조회 결과가 없습니다."
    if query_key == "status":
        return f"현재 운영 상태를 조회했습니다: {rows[:1200]}"
    return f"{query_key} 항목을 조회했습니다: {rows[:1200]}"


def answer_question(text: str, *, chat_id: str = "") -> Answer:
    classified = classify(text)
    query_key = str(classified["query_key"])
    rows = db_scalar(SAFE_QUERIES[query_key])
    summary = summarize(text, query_key, rows)
    reply = str(summary.get("reply") or "").strip() or deterministic_reply(query_key, rows)
    raw_model = {"classification": classified, "summary": summary}
    db_exec(
        "INSERT INTO telegram_natural_language_queries(chat_id,message_text,intent,safe_query_key,provider,model,response_text,raw_model) "
        "VALUES(NULLIF(%s,'')::bigint,%s,'db_query',%s,'ollama-local','qwen3.5:4b',%s,%s::jsonb);",
        (chat_id, text, query_key, reply, json.dumps(raw_model, ensure_ascii=False)),
    )
    return Answer(query_key=query_key, response_text=reply, raw_model=raw_model)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    answer = answer_question(args.question, chat_id=args.chat_id)
    if args.json:
        print(json.dumps(answer.__dict__, ensure_ascii=False))
    else:
        print(answer.response_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
