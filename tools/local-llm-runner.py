#!/usr/bin/env python3
"""Run evidence-backed, non-repeating local Atemoya LLM jobs."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB_CMD = ["/usr/local/bin/docker", "exec", "atemoya-postgres", "psql", "-U", "n8n", "-d", "n8n", "-At", "-F", "\t"]
MODEL = os.getenv("ATEMOYA_LOCAL_MODEL", "qwen3.5:4b")
OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
N8N_NOTIFY = os.getenv("N8N_NOTIFY_URL", "http://127.0.0.1:5678/webhook/atemoya-local-llm-result")
SOURCE_FILE = ROOT / "tools/source-scout-latest.json"
DEDUP_FILE = ROOT / "tools/local-llm-notify-dedupe.json"
STATUS_FILE = ROOT / "tools/local-llm-status.json"
TOPIC_COOLDOWN_DAYS = int(os.getenv("ATEMOYA_TOPIC_COOLDOWN_DAYS", "7"))

CHANNEL_WEIGHT = {"google-news": 30, "reddit": 20, "hackernews": 10}
KEYWORDS = {
    "shopping": 12, "shopper": 12, "commerce": 12, "retail": 10,
    "payment": 8, "affiliate": 10, "creator": 7, "consumer": 8,
    "product": 7, "review": 7, "price": 7, "cost": 6, "tool": 5,
    "쇼핑": 12, "커머스": 12, "소비자": 8, "구매": 10, "가격": 7,
}


def db_output(statement):
    return subprocess.run(DB_CMD + ["-c", statement], capture_output=True, text=True, check=True).stdout.strip()


def sql(statement, args=()):
    values = [str(x).replace("'", "''") if x is not None else "" for x in args]
    rendered = statement.replace("?", "\x00")
    for value in values:
        rendered = rendered.replace("\x00", "'" + value + "'", 1)
    subprocess.run(DB_CMD + ["-c", rendered], check=True, stdout=subprocess.DEVNULL)


def snapshot():
    sql("UPDATE local_llm_runs SET status='error',progress=100,current_step='시간 초과 정리',error_summary='작업이 15분 이상 갱신되지 않아 자동 정리됨',updated_at=NOW() WHERE status='running' AND updated_at < NOW()-interval '15 minutes'; UPDATE local_llm_runs SET status='error',progress=100,current_step='대기 만료 정리',error_summary='대기열에서 1시간 이상 대기하여 자동 정리됨',updated_at=NOW() WHERE status='queued' AND updated_at < NOW()-interval '1 hour';")
    raw = db_output("SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT lane,task_name,model,provider,status,progress,current_step,result_summary,error_summary,started_at,finished_at,duration_ms FROM local_llm_runs ORDER BY updated_at DESC LIMIT 20) x;") or "[]"
    try:
        runs = json.loads(raw)
    except Exception:
        runs = []
    STATUS_FILE.write_text(json.dumps({"model": MODEL, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_title(title):
    return re.sub(r"[^0-9a-zA-Z가-힣]+", " ", title.lower()).strip()


def title_tokens(title):
    stop = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with", "new", "introduces", "launches"}
    return {token for token in normalize_title(title).split() if len(token) > 1 and token not in stop}


def similar_title(left, right, threshold=0.4):
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return False
    overlap = len(a & b)
    return overlap / len(a | b) >= threshold or overlap / min(len(a), len(b)) >= 0.7


def topic_key(title, url):
    return hashlib.sha256((normalize_title(title) + "|" + url).encode()).hexdigest()[:20]


def load_candidates(now=None):
    if not SOURCE_FILE.exists():
        return []
    now = now or time.time()
    if now - SOURCE_FILE.stat().st_mtime > 4 * 3600:
        return []
    data = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    candidates = []
    seen = set()
    for source in data.get("sources", []):
        channel = source.get("channel", "unknown")
        for item in source.get("items", []):
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if not title or not url:
                continue
            key = topic_key(title, url)
            if key in seen:
                continue
            seen.add(key)
            lowered = title.lower()
            score = CHANNEL_WEIGHT.get(channel, 0) + sum(weight for word, weight in KEYWORDS.items() if word in lowered)
            candidates.append({"topic_key": key, "title": title[:500], "url": url[:2000], "channel": channel, "score": score})
    return sorted(candidates, key=lambda row: (-row["score"], row["title"]))


def recent_topic_keys(days=TOPIC_COOLDOWN_DAYS):
    raw = db_output("SELECT COALESCE(json_agg(topic_key),'[]'::json) FROM (SELECT DISTINCT metadata->>'topic_key' AS topic_key FROM local_llm_runs WHERE updated_at > NOW()-interval '%d days' AND COALESCE(metadata->>'topic_key','') <> '') x;" % days) or "[]"
    return set(json.loads(raw))


def recent_topic_titles(days=TOPIC_COOLDOWN_DAYS):
    raw = db_output("SELECT COALESCE(json_agg(topic_title),'[]'::json) FROM (SELECT DISTINCT metadata->>'topic_title' AS topic_title FROM local_llm_runs WHERE updated_at > NOW()-interval '%d days' AND COALESCE(metadata->>'topic_title','') <> '') x;" % days) or "[]"
    return json.loads(raw)


def plan_jobs(candidates, used_keys, used_titles=()):
    comparison_titles = list(used_titles)

    def eligible(item, selected):
        if item["topic_key"] in used_keys:
            return False
        if any(item["topic_key"] == row["topic_key"] for row in selected):
            return False
        titles = comparison_titles + [row["title"] for row in selected]
        return not any(similar_title(item["title"], title) for title in titles)

    fresh = []
    first = next((item for item in candidates if eligible(item, fresh)), None)
    if first:
        fresh.append(first)
        second = next(
            (
                item
                for item in candidates
                if item["channel"] != first["channel"] and eligible(item, fresh)
            ),
            None,
        )
        if second is None:
            second = next((item for item in candidates if eligible(item, fresh)), None)
        if second:
            fresh.append(second)
    if not fresh:
        return []
    templates = [
        ("research", "근거 기반 트렌드 평가", 260,
         "아래 수집 근거 하나만 사용하라. 최신 사실이나 수치를 추가로 지어내지 마라. 관찰된 내용, Atemoya 수익화 관련성, 24시간 안에 할 수 있는 저비용 실험 1개, 검증 지표를 한국어 5개 불릿 이내로 작성하고 마지막에 제공된 근거 URL을 그대로 적어라."),
        ("content", "신규 수익 콘텐츠 후보", 220,
         "아래 수집 근거 하나만 사용하라. 사실과 추론을 구분하고 확인되지 않은 제품 성능이나 수치를 만들지 마라. 대상 독자, 검색 의도, 페이지 또는 도구 아이디어 1개, 과장 없는 제목 3개를 한국어 5개 불릿 이내로 작성하고 마지막에 제공된 근거 URL을 그대로 적어라."),
    ]
    jobs = []
    for item, (lane, task, max_tokens, instruction) in zip(fresh, templates):
        prompt = "%s\n\n[수집 채널] %s\n[근거 제목] %s\n[근거 URL] %s" % (instruction, item["channel"], item["title"], item["url"])
        jobs.append({"lane": lane, "task": task, "max_tokens": max_tokens, "prompt": prompt, **item})
    return jobs


def update(run_key, status, progress, step, summary=None, error=None, started=None, finished=None, duration=None, out_tokens=None):
    sql("UPDATE local_llm_runs SET status=?,progress=?,current_step=?,result_summary=NULLIF(?,''),error_summary=NULLIF(?,''),started_at=COALESCE(started_at,NULLIF(?,'')::timestamptz),finished_at=NULLIF(?,'')::timestamptz,duration_ms=NULLIF(?, '')::int,output_tokens=NULLIF(?, '')::int,updated_at=NOW() WHERE run_key=?", (status, progress, step, summary, error, started, finished, duration, out_tokens, run_key))
    snapshot()


def notify(job, duration, summary, error=None):
    day = time.strftime("%Y-%m-%d", time.localtime())
    key = hashlib.sha256((job["task"] + "|" + job["topic_key"] + "|" + day).encode()).hexdigest()
    try:
        old = json.loads(DEDUP_FILE.read_text(encoding="utf-8"))
    except Exception:
        old = {}
    previous = old.get(job["task"])
    previous_key = previous.get("key") if isinstance(previous, dict) else previous
    if previous_key == key:
        return False
    payload = json.dumps({"task_name": job["task"] + " · " + job["title"][:80], "provider": "ollama-local", "model": MODEL, "duration_ms": duration, "result_summary": summary, "error_summary": error or ""}).encode()
    try:
        urlopen(Request(N8N_NOTIFY, data=payload, headers={"Content-Type": "application/json"}), timeout=10).read()
        old[job["task"]] = {"key": key, "topic_key": job["topic_key"], "notified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        DEDUP_FILE.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print("telegram notify skipped:", exc)
        return False


def worker(job):
    run_key = "%s-%s" % (job["lane"], uuid.uuid4().hex[:10])
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata = json.dumps({"runner": "tools/local-llm-runner.py", "runner_version": 2, "topic_key": job["topic_key"], "topic_title": job["title"], "topic_url": job["url"], "source_channel": job["channel"], "cooldown_days": TOPIC_COOLDOWN_DAYS}, ensure_ascii=False)
    sql("INSERT INTO local_llm_runs(run_key,lane,task_name,model,provider,inference_note,status,progress,current_step,started_at,metadata) VALUES(?,?,?,?,?,?,?,?,?,?::timestamptz,?::jsonb)", (run_key, job["lane"], job["task"], MODEL, "ollama-local", "로컬 iMac Ollama 추론 · 수집 근거 제한 · 외부 API 미사용", "queued", 0, "근거 확인", started, metadata))
    snapshot()
    update(run_key, "running", 10, "로컬 Ollama 근거 기반 추론", started=started)
    began = time.time()
    try:
        body = json.dumps({"model": MODEL, "stream": False, "think": False, "options": {"num_predict": job["max_tokens"], "temperature": 0.15}, "messages": [{"role": "system", "content": "Atemoya의 한국어 커머스 분석 보조다. 제공된 근거만 사용하고 사실과 추론을 구분한다. 근거 URL을 반드시 포함한다."}, {"role": "user", "content": job["prompt"]}]}).encode()
        response = json.loads(urlopen(Request(OLLAMA, data=body, headers={"Content-Type": "application/json"}), timeout=180).read())
        text = (response.get("message") or {}).get("content", "").strip()
        if job["url"] not in text:
            text += "\n- 근거 URL: " + job["url"]
        duration = int((time.time() - began) * 1000)
        final = "[추론: Ollama 로컬 / %s]\n[수집: %s]\n[근거: %s]\n%s" % (MODEL, job["channel"], job["url"], text[:1600])
        update(run_key, "complete", 100, "근거 검증 완료", summary=final, finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), duration=duration, out_tokens=response.get("eval_count"))
        notify(job, duration, final)
    except Exception as exc:
        update(run_key, "error", 100, "오류", error=str(exc)[:800], finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), duration=int((time.time() - began) * 1000))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Select topics without DB writes, Ollama calls, or Telegram notifications")
    args = parser.parse_args()
    candidates = load_candidates()
    used = set() if args.dry_run else recent_topic_keys()
    used_titles = [] if args.dry_run else recent_topic_titles()
    jobs = plan_jobs(candidates, used, used_titles)
    if args.dry_run:
        print(json.dumps({"candidate_count": len(candidates), "jobs": [{k: job[k] for k in ("lane", "task", "title", "url", "channel", "topic_key", "score")} for job in jobs]}, ensure_ascii=False, indent=2))
        return
    if not jobs:
        print(json.dumps({"model": MODEL, "jobs": 0, "status": "no_fresh_evidence", "notification": "skipped"}, ensure_ascii=False))
        return
    # Sequential execution prevents Ollama jobs from competing for 16 GB unified memory.
    for job in jobs:
        worker(job)
    print(json.dumps({"model": MODEL, "jobs": len(jobs), "status": "finished"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
