#!/usr/bin/env python3
"""Deterministic Atemoya watchdog with allow-listed recovery and incident dedup."""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "tools/source-scout-latest.json"
STATE_FILE = ROOT / "tools/ops-watchdog-state.json"
DB_CMD = ["/usr/local/bin/docker", "exec", "atemoya-postgres", "psql", "-U", "n8n", "-d", "n8n", "-At"]
INCIDENT_WEBHOOK = "http://127.0.0.1:5678/webhook/atemoya-ops-incident"
CONTAINERS = ("atemoya-postgres", "atemoya-n8n", "atemoya-webhook-proxy")
REMEDIATION_COOLDOWN = 3600


@dataclass
class Check:
    component: str
    code: str
    status: str
    message: str
    latency_ms: Optional[int] = None
    details: Optional[dict] = None
    remediated: bool = False
    remediation_action: Optional[str] = None

    @property
    def fingerprint(self):
        return f"{self.component}|{self.code}"


def command(args, timeout=20):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def http_ok(url, timeout=3):
    started = time.monotonic()
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(4096)
            return 200 <= response.status < 300, int((time.monotonic() - started) * 1000), body.decode("utf-8", "replace")
    except Exception as exc:
        return False, int((time.monotonic() - started) * 1000), str(exc)


def sql_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def db_scalar(statement):
    result = command(DB_CMD + ["-c", statement], timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PostgreSQL query failed")
    return result.stdout.strip()


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_remediation": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def container_check(name):
    result = command(["/usr/local/bin/docker", "inspect", "-f", "{{.State.Running}}|{{.State.Status}}", name])
    if result.returncode:
        return Check("docker", f"container:{name}", "bad", f"{name} 컨테이너를 찾을 수 없음", details={"error": result.stderr.strip()[:300]})
    running, _, state = result.stdout.strip().partition("|")
    status = "good" if running == "true" else "bad"
    return Check("docker", f"container:{name}", status, f"{name}: {state}", details={"running": running == "true", "state": state})


def source_check(now=None):
    now = now or time.time()
    if not SOURCE_FILE.exists():
        return Check("collection", "source_freshness", "bad", "수집 상태 파일 없음")
    age = int(now - SOURCE_FILE.stat().st_mtime)
    try:
        payload = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
        source_count = len(payload.get("sources", []))
        item_count = sum(len(row.get("items", [])) for row in payload.get("sources", []))
    except Exception as exc:
        return Check("collection", "source_freshness", "bad", "수집 상태 JSON 손상", details={"error": str(exc)[:300]})
    if age > 3 * 3600:
        status = "bad"
    elif age > 2 * 3600 or source_count < 2 or item_count == 0:
        status = "review"
    else:
        status = "good"
    return Check("collection", "source_freshness", status, f"수집 {source_count}채널·{item_count}항목·{age // 60}분 전", details={"age_seconds": age, "sources": source_count, "items": item_count})


def memory_pressure_check():
    result = command(["/usr/bin/memory_pressure", "-Q"])
    match = re.search(r"free percentage:\s*(\d+)%", result.stdout)
    if result.returncode or not match:
        return Check("host", "memory_pressure", "review", "메모리 압력 확인 실패", details={"output": (result.stderr or result.stdout).strip()[:300]})
    free_percent = int(match.group(1))
    status = "bad" if free_percent < 10 else "review" if free_percent < 20 else "good"
    return Check("host", "memory_pressure", status, f"메모리 여유 {free_percent}%", details={"free_percent": free_percent})


def collect_checks():
    checks = [container_check(name) for name in CONTAINERS]
    ok, latency, detail = http_ok("http://127.0.0.1:5678/healthz")
    checks.append(Check("n8n", "healthz", "good" if ok else "bad", "n8n HTTP 정상" if ok else "n8n HTTP 응답 실패", latency, {"response": detail[:300]}))
    ok, latency, detail = http_ok("http://127.0.0.1:11434/api/tags")
    checks.append(Check("ollama", "api", "good" if ok else "bad", "Ollama API 정상" if ok else "Ollama API 응답 실패", latency, {"response": detail[:300]}))
    try:
        value = db_scalar("SELECT 1;")
        checks.append(Check("postgres", "query", "good" if value == "1" else "bad", "PostgreSQL 쿼리 정상" if value == "1" else "PostgreSQL 응답 이상"))
        stale = int(db_scalar("SELECT count(*) FROM local_llm_runs WHERE (status='running' AND updated_at<NOW()-interval '20 minutes') OR (status='queued' AND updated_at<NOW()-interval '70 minutes');") or 0)
        checks.append(Check("local-llm", "stale_jobs", "bad" if stale else "good", f"정체 작업 {stale}건", details={"count": stale}))
        age = int(db_scalar("SELECT COALESCE(EXTRACT(EPOCH FROM (NOW()-max(updated_at)))::bigint,-1) FROM local_llm_runs WHERE status='complete';") or -1)
        status = "bad" if age < 0 or age > 4 * 3600 else "review" if age > 3 * 3600 else "good"
        checks.append(Check("local-llm", "freshness", status, "최근 완료 없음" if age < 0 else f"최근 완료 {age // 60}분 전", details={"age_seconds": age}))
        errors = int(db_scalar("SELECT count(*) FROM execution_entity WHERE status='error' AND \"startedAt\">NOW()-interval '2 hours';") or 0)
        checks.append(Check("n8n", "recent_errors", "bad" if errors >= 3 else "review" if errors else "good", f"최근 2시간 n8n 오류 {errors}건", details={"count": errors}))
    except Exception as exc:
        checks.append(Check("postgres", "query", "bad", "PostgreSQL 상태 조회 실패", details={"error": str(exc)[:300]}))
    checks.append(source_check())
    free_gb = shutil.disk_usage(ROOT).free / (1024 ** 3)
    checks.append(Check("host", "disk_free", "bad" if free_gb < 5 else "review" if free_gb < 10 else "good", f"디스크 여유 {free_gb:.1f}GB", details={"free_gb": round(free_gb, 1)}))
    checks.append(memory_pressure_check())
    return checks


def may_remediate(state, key, now=None):
    now = now or time.time()
    return now - float(state.get("last_remediation", {}).get(key, 0)) >= REMEDIATION_COOLDOWN


def remediate(checks, state):
    actions = []
    now = time.time()
    for check in checks:
        if check.status == "good" or not may_remediate(state, check.fingerprint, now):
            continue
        action = None
        if check.component == "docker" and check.code.startswith("container:") and check.details and not check.details.get("running"):
            name = check.code.split(":", 1)[1]
            result = command(["/usr/local/bin/docker", "start", name], timeout=60)
            if result.returncode == 0:
                action = f"docker start {name}"
        elif check.component == "n8n" and check.code == "healthz":
            result = command(["/usr/local/bin/docker", "restart", "atemoya-n8n"], timeout=90)
            if result.returncode == 0:
                action = "docker restart atemoya-n8n"
        elif check.component == "collection" and check.code == "source_freshness":
            uid = str(os.getuid())
            result = command(["/bin/launchctl", "kickstart", "-k", f"gui/{uid}/com.atemoya.source-scout"], timeout=30)
            if result.returncode == 0:
                action = "launchctl kickstart com.atemoya.source-scout"
        elif check.component == "local-llm" and check.code == "stale_jobs" and check.details and check.details.get("count", 0):
            db_scalar("UPDATE local_llm_runs SET status='error',progress=100,current_step='Watchdog 정리',error_summary='정체 작업 자동 정리',updated_at=NOW() WHERE (status='running' AND updated_at<NOW()-interval '20 minutes') OR (status='queued' AND updated_at<NOW()-interval '70 minutes');")
            action = "stale local_llm_runs marked error"
        if action:
            state.setdefault("last_remediation", {})[check.fingerprint] = now
            actions.append((check.fingerprint, action))
    if actions:
        save_state(state)
        time.sleep(5)
    return actions


def persist_check(check):
    details = json.dumps(check.details or {}, ensure_ascii=False)
    statement = (
        "INSERT INTO system_health_checks(component,check_code,status,message,latency_ms,remediated,remediation_action,details) VALUES("
        + ",".join([sql_quote(check.component), sql_quote(check.code), sql_quote(check.status), sql_quote(check.message), "NULL" if check.latency_ms is None else str(check.latency_ms), "true" if check.remediated else "false", "NULL" if not check.remediation_action else sql_quote(check.remediation_action), sql_quote(details) + "::jsonb"]) + ");"
    )
    db_scalar(statement)


def transition_incident(check):
    existing = db_scalar("SELECT COALESCE(state,'') FROM system_incidents WHERE fingerprint=" + sql_quote(check.fingerprint) + ";")
    details = sql_quote(json.dumps(check.details or {}, ensure_ascii=False)) + "::jsonb"
    if check.status == "good":
        if existing == "open":
            db_scalar("UPDATE system_incidents SET state='resolved',resolved_at=NOW(),last_seen_at=NOW(),details=" + details + " WHERE fingerprint=" + sql_quote(check.fingerprint) + ";")
            return {"transition": "resolved", "check": check}
        return None
    if existing == "open":
        db_scalar("UPDATE system_incidents SET severity=" + sql_quote(check.status) + ",last_seen_at=NOW(),occurrence_count=occurrence_count+1,title=" + sql_quote(check.message) + ",details=" + details + " WHERE fingerprint=" + sql_quote(check.fingerprint) + ";")
        return None
    db_scalar("INSERT INTO system_incidents(fingerprint,component,check_code,severity,state,title,details) VALUES(" + ",".join([sql_quote(check.fingerprint), sql_quote(check.component), sql_quote(check.code), sql_quote(check.status), "'open'", sql_quote(check.message), details]) + ") ON CONFLICT(fingerprint) DO UPDATE SET severity=EXCLUDED.severity,state='open',title=EXCLUDED.title,last_seen_at=NOW(),resolved_at=NULL,occurrence_count=system_incidents.occurrence_count+1,details=EXCLUDED.details;")
    return {"transition": "opened", "check": check}


def notify(transitions):
    if not transitions:
        return False
    lines = []
    worst = "GOOD"
    for row in transitions:
        check = row["check"]
        if row["transition"] == "resolved":
            lines.append(f"✅ 복구 · {check.component}/{check.code}: {check.message}")
        else:
            icon = "🚨" if check.status == "bad" else "⚠️"
            lines.append(f"{icon} 발생 · {check.component}/{check.code}: {check.message}")
            worst = "BAD" if check.status == "bad" else "REVIEW" if worst == "GOOD" else worst
    payload = json.dumps({"status": worst, "summary": "\n".join(lines)[:3500], "source": "atemoya-ops-watchdog"}, ensure_ascii=False).encode()
    try:
        urlopen(Request(INCIDENT_WEBHOOK, data=payload, headers={"Content-Type": "application/json"}), timeout=10).read()
        for row in transitions:
            db_scalar("UPDATE system_incidents SET last_notified_at=NOW() WHERE fingerprint=" + sql_quote(row["check"].fingerprint) + ";")
        return True
    except Exception as exc:
        print("incident notification deferred:", exc)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-remediate", action="store_true")
    args = parser.parse_args()
    initial = collect_checks()
    if args.dry_run:
        print(json.dumps({"checks": [asdict(row) for row in initial]}, ensure_ascii=False, indent=2))
        return 0 if all(row.status == "good" for row in initial) else 1
    state = load_state()
    actions = [] if args.no_remediate else remediate(initial, state)
    final = collect_checks() if actions else initial
    action_map = dict(actions)
    transitions = []
    for check in final:
        if check.fingerprint in action_map:
            check.remediated = check.status == "good"
            check.remediation_action = action_map[check.fingerprint]
        persist_check(check)
        transition = transition_incident(check)
        if transition:
            transitions.append(transition)
    notify(transitions)
    print(json.dumps({"status": "BAD" if any(row.status == "bad" for row in final) else "REVIEW" if any(row.status == "review" for row in final) else "GOOD", "actions": actions, "transitions": [row["transition"] + ":" + row["check"].fingerprint for row in transitions], "checks": [asdict(row) for row in final]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
