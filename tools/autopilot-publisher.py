#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render approved Atemoya drafts, push the feature branch, and detect Pages release."""
import argparse
import html
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB_CMD = ["/usr/local/bin/docker", "exec", "atemoya-postgres", "psql", "-U", "n8n", "-d", "n8n", "-At"]
BRANCH = "feat/atemoya-ops-baseline"
BASE_URL = "https://orange3718.github.io/Banana/autopilot/"
COMPARE_URL = "https://github.com/Orange3718/Banana/compare/main...feat/atemoya-ops-baseline?expand=1"
NOTIFY_URL = "http://127.0.0.1:5678/webhook/atemoya-autopilot-publisher"
LOCK = Path("/tmp/atemoya-autopilot-publisher.lock")
NODE_CANDIDATES = [
    Path("/opt/homebrew/bin/node"),
    Path("/usr/local/bin/node"),
    Path("/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node"),
]


def command(args, timeout=120):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def node_binary():
    for candidate in NODE_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Node.js runtime not found")


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def db(statement):
    result = command(DB_CMD + ["-c", statement], timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PostgreSQL query failed")
    return result.stdout.strip()


def db_json(statement):
    raw = db("SELECT COALESCE(json_agg(x),'[]'::json) FROM (" + statement + ") x;") or "[]"
    return json.loads(raw)


def safe_slug(value):
    value = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return (value[:72] or "atemoya-brief")


def sanitize_body(value):
    body = str(value or "")
    body = re.sub(r"<\s*(script|style|iframe)[^>]*>[\s\S]*?<\s*/\s*\1\s*>", "", body, flags=re.I)
    body = re.sub(r"\s+on[a-z]+\s*=\s*(['\"]).*?\1", "", body, flags=re.I)
    body = re.sub(r"javascript\s*:", "", body, flags=re.I)
    return body.strip()


def render_page(row):
    meta = row.get("content_metadata") or {}
    title = str(row.get("title") or "Atemoya 구매 판단 브리프")[:120]
    description = str(meta.get("description") or "공개 근거를 바탕으로 구매와 사업 판단에 필요한 질문을 정리합니다.")[:180]
    slug = safe_slug(meta.get("slug") or row.get("job_key"))
    source_url = str(row.get("source_url") or meta.get("source_url") or "")
    body = sanitize_body(meta.get("body_html"))
    if len(re.sub(r"<[^>]+>", " ", body)) < 500:
        raise ValueError("approved body is too short")
    canonical = BASE_URL + slug + ".html"
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{html.escape(description, quote=True)}"><link rel="canonical" href="{html.escape(canonical, quote=True)}"><title>{html.escape(title)} | Atemoya</title><link rel="stylesheet" href="../assets/story.css"><script src="../config.js"></script><script defer src="../assets/analytics.js"></script><script defer src="../assets/story.js"></script></head><body><header><div class="wrap nav"><a class="brand" href="../index.html">ATEMOYA</a><a href="../tools/index.html">무료 Tools</a></div></header><main class="wrap"><article><div class="category">EVIDENCE-BASED COMMERCE BRIEF</div><h1>{html.escape(title)}</h1><p class="dek">{html.escape(description)}</p>{body}<section><h2>근거와 한계</h2><p>이 글은 공개 자료 한 건과 로컬 AI 정리를 바탕으로 작성됐습니다. 확인되지 않은 판매량·성능·수익을 사실로 단정하지 않습니다.</p><p><a href="{html.escape(source_url, quote=True)}" rel="noopener noreferrer">원문 근거 확인</a></p></section><section class="toolCta"><h2>숫자로 다시 확인하세요</h2><p>구매 전에는 가격뿐 아니라 유지비·용량·사용 조건을 함께 비교해야 합니다.</p><a class="button" href="../tools/index.html">Atemoya 무료 계산 도구 보기</a></section></article></main></body></html>'''
    return slug, document


def write_index():
    rows = db_json("SELECT c.title,j.artifact_path,j.stage FROM revenue_autopilot_jobs j JOIN content c ON c.id=j.content_id WHERE j.artifact_path IS NOT NULL AND j.stage IN ('rendering','branch_ready','published') ORDER BY j.updated_at DESC")
    cards = "".join(
        '<a class="card" href="' + html.escape(Path(row["artifact_path"]).name, quote=True) + '"><div class="cardText"><span>근거 기반 자동화</span><b>' + html.escape(row["title"]) + '</b><p>공개 근거와 구매 판단 질문을 함께 확인합니다.</p></div></a>'
        for row in rows
    ) or '<p>승인된 브리프를 준비하고 있습니다.</p>'
    page = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Atemoya의 근거 기반 커머스 브리프입니다."><title>근거 기반 커머스 브리프 | Atemoya</title><link rel="stylesheet" href="../assets/story.css"><script src="../config.js"></script><script defer src="../assets/analytics.js"></script></head><body><header><div class="wrap nav"><a class="brand" href="../index.html">ATEMOYA</a><a href="../tools/index.html">무료 Tools</a></div></header><main class="wrap"><h1>근거 기반 커머스 브리프</h1><p class="dek">과장된 추천보다 출처와 확인 질문을 먼저 제공합니다.</p><section class="cards">' + cards + '</section></main></body></html>'
    directory = ROOT / "autopilot"
    directory.mkdir(exist_ok=True)
    (directory / "index.html").write_text(page, encoding="utf-8")


def notify(status, summary, url=""):
    payload = json.dumps({"status": status, "summary": summary, "url": url, "provider": "local-publisher"}, ensure_ascii=False).encode()
    try:
        urlopen(Request(NOTIFY_URL, data=payload, headers={"Content-Type": "application/json"}), timeout=10).read()
    except Exception as exc:
        print("publisher notification deferred:", exc)


def detect_publications():
    rows = db_json("SELECT id,job_key,artifact_path,content_id FROM revenue_autopilot_jobs WHERE stage='branch_ready' AND artifact_path IS NOT NULL ORDER BY id")
    for row in rows:
        url = BASE_URL + Path(row["artifact_path"]).name
        try:
            with urlopen(url, timeout=10) as response:
                live = response.status == 200
        except Exception:
            live = False
        if live:
            db("UPDATE revenue_autopilot_jobs SET stage='published',result_url=" + quote(url) + ",finished_at=NOW(),updated_at=NOW() WHERE id=" + str(row["id"]) + "; UPDATE content SET status='published',published_url=" + quote(url) + ",published_at=NOW(),updated_at=NOW() WHERE id=" + str(row["content_id"]) + ";")
            notify("PUBLISHED", "승인된 페이지가 GitHub Pages에서 공개됐습니다.", url)


def publish_one(dry_run=False):
    rows = db_json("SELECT j.id,j.job_key,j.content_id,c.title,c.source_url,c.metadata AS content_metadata FROM revenue_autopilot_jobs j JOIN content c ON c.id=j.content_id WHERE j.stage='approved' ORDER BY j.priority DESC,j.id LIMIT 1")
    if not rows:
        return None
    row = rows[0]
    slug, document = render_page(row)
    relative = "autopilot/" + slug + ".html"
    if dry_run:
        return {"job_id": row["id"], "artifact_path": relative, "bytes": len(document.encode())}
    db("UPDATE revenue_autopilot_jobs SET stage='rendering',attempt=attempt+1,updated_at=NOW() WHERE id=" + str(row["id"]) + ";")
    try:
        directory = ROOT / "autopilot"
        directory.mkdir(exist_ok=True)
        (ROOT / relative).write_text(document, encoding="utf-8")
        db("UPDATE revenue_autopilot_jobs SET artifact_path=" + quote(relative) + ",updated_at=NOW() WHERE id=" + str(row["id"]) + ";")
        write_index()
        node = node_binary()
        checks = [
            command([node, "scripts/build-sitemap.mjs"]),
            command([node, "scripts/test-site.mjs"]),
        ]
        if any(result.returncode for result in checks):
            raise RuntimeError("site validation failed: " + " | ".join((result.stderr or result.stdout).strip()[-500:] for result in checks if result.returncode))
        current = command(["git", "branch", "--show-current"])
        if current.stdout.strip() != BRANCH:
            raise RuntimeError("publisher refuses non-feature branch")
        staged = command(["git", "diff", "--cached", "--name-only"])
        if staged.returncode:
            raise RuntimeError(staged.stderr.strip())
        if staged.stdout.strip():
            raise RuntimeError("publisher refuses a worktree with pre-staged files")
        paths = [relative, "autopilot/index.html", "sitemap.xml"]
        result = command(["git", "add", "--"] + paths)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        result = command(["git", "commit", "-m", "content: add approved Atemoya brief " + slug])
        if result.returncode and "nothing to commit" not in (result.stdout + result.stderr).lower():
            raise RuntimeError((result.stderr or result.stdout).strip())
        result = command(["git", "push", "origin", BRANCH], timeout=180)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip())
        db("UPDATE revenue_autopilot_jobs SET stage='branch_ready',artifact_path=" + quote(relative) + ",result_url=" + quote(COMPARE_URL) + ",last_error=NULL,updated_at=NOW() WHERE id=" + str(row["id"]) + "; UPDATE content SET status='approved',body_ref=" + quote(relative) + ",updated_at=NOW() WHERE id=" + str(row["content_id"]) + ";")
        notify("BRANCH_READY", "승인 콘텐츠의 HTML 생성·검증·feature branch push가 완료됐습니다. PR 생성 또는 병합 후 공개 여부를 자동 감지합니다.", COMPARE_URL)
        return {"job_id": row["id"], "artifact_path": relative, "result_url": COMPARE_URL}
    except Exception as exc:
        message = str(exc)[:1000]
        db("UPDATE revenue_autopilot_jobs SET stage=CASE WHEN attempt>=max_attempts THEN 'failed' ELSE 'retry' END,next_attempt_at=NOW()+interval '1 hour',last_error=" + quote(message) + ",updated_at=NOW() WHERE id=" + str(row["id"]) + ";")
        if int(db("SELECT attempt FROM revenue_autopilot_jobs WHERE id=" + str(row["id"]) + ";") or 0) >= 3:
            notify("FAILED", "Publisher가 3회 실패했습니다: " + message)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 900:
        print("skip: publisher lock active")
        return 0
    LOCK.write_text(str(time.time()))
    try:
        detect_publications()
        result = publish_one(args.dry_run)
        print(json.dumps({"status": "idle" if result is None else "processed", "result": result}, ensure_ascii=False))
    finally:
        LOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
