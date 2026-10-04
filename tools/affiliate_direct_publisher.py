#!/usr/bin/env python3
"""Deterministic, approval-free publisher for pre-verified Coupang content.

The worker never invents a product, URL, claim, or schedule. PostgreSQL is the
runtime source of truth, while the reviewed JSON manifest is the immutable
content source. A detached Git worktree keeps publication commits isolated from
the operator's development worktree.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "ops/affiliate-publication/coupang-volume-pilot-20260914.json"
PUBLIC_WORKTREE = Path(os.environ.get("ATEMOYA_PUBLIC_WORKTREE", "/Users/orange/Atemoya/runtime/banana-public"))
DB_CMD = [
    "/usr/local/bin/docker", "exec", "atemoya-postgres", "psql",
    "-v", "ON_ERROR_STOP=1", "-U", "n8n", "-d", "n8n", "-At",
]
LOCK = Path("/tmp/atemoya-affiliate-direct-publisher.lock")
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
NODE_CANDIDATES = [
    Path("/opt/homebrew/bin/node"),
    Path("/usr/local/bin/node"),
    Path("/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node"),
]
VERIFIED_LINKS = {
    "68486824": "https://link.coupang.com/a/g0MPccSO4q",
    "8631363798": "https://link.coupang.com/a/g04vJvRZbE",
    "8825604493": "https://link.coupang.com/a/g1u9WjvvwW",
    "4888844473": "https://link.coupang.com/a/g1vbMa9ZT2",
    "9200898827": "https://link.coupang.com/a/g1vcnJyb6G",
    "8190513175": "https://link.coupang.com/a/g1vcY61Nts",
    "9148856386": "https://link.coupang.com/a/g1vjmR0GUm",
    "8957394071": "https://link.coupang.com/a/g1vkxjLeoe",
    "8481268931": "https://link.coupang.com/a/g1vlHY0xHg",
    "9217314286": "https://link.coupang.com/a/g1vmR9I9ng",
}


class PermanentError(RuntimeError):
    """A content, policy, or integrity failure that must stop the batch."""


class DeploymentPending(RuntimeError):
    """The commit was pushed but the public edge has not converged yet."""


def command(args: list[str], cwd: Path = ROOT, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def require_command(args: list[str], cwd: Path = ROOT, timeout: int = 180) -> str:
    result = command(args, cwd=cwd, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail[-1500:] or f"command failed: {args[0]}")
    return result.stdout.strip()


def node_binary() -> str:
    for candidate in NODE_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    raise PermanentError("Node.js runtime not found")


def quote(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def db(statement: str) -> str:
    return require_command(DB_CMD + ["-c", statement], timeout=30)


def db_json(statement: str) -> list[dict[str, Any]]:
    raw = db("SELECT COALESCE(json_agg(x),'[]'::json) FROM (" + statement + ") x;") or "[]"
    value = json.loads(raw)
    if not isinstance(value, list):
        raise RuntimeError("PostgreSQL returned a non-list JSON value")
    return value


def db_row(statement: str) -> dict[str, Any] | None:
    raw = db(statement).strip()
    if not raw:
        return None
    value = json.loads(raw.splitlines()[-1])
    if not isinstance(value, dict):
        raise RuntimeError("PostgreSQL returned a non-object JSON value")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_deployed_html(value: str) -> str:
    """Remove only the allowlisted CI-owned verification meta transforms."""
    tag = r'<meta name="(?:google|naver)-site-verification" content="[A-Za-z0-9_-]{10,120}">'
    pattern = tag + rf'(?=(?:{tag})*</head>)'
    providers = re.findall(r'<meta name="(google|naver)-site-verification"', value)
    normalized = re.sub(pattern, "", value)
    if "site-verification" in normalized or len(providers) > 2 or len(set(providers)) != len(providers):
        raise PermanentError("unexpected site-verification transform in deployed HTML")
    return normalized


def item_digest(item: dict[str, Any]) -> str:
    return sha256_text(canonical_json(item))


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)


def parse_schedule(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PermanentError(f"invalid scheduled_at: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PermanentError(f"scheduled_at requires an explicit timezone: {value}")
    if int(parsed.utcoffset().total_seconds()) != 9 * 3600:
        raise PermanentError(f"scheduled_at must use Asia/Seoul +09:00: {value}")
    return parsed


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PermanentError(f"manifest cannot be read: {path}: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise PermanentError("unsupported publication manifest schema")
    if manifest.get("authorization_mode") != "direct_user_instruction":
        raise PermanentError("direct publisher requires direct_user_instruction authorization")
    if manifest.get("target") != "github_pages:Orange3718/Banana":
        raise PermanentError("publication target is not allowlisted")
    if manifest.get("base_url") != "https://orange3718.github.io/Banana/":
        raise PermanentError("base_url is not allowlisted")
    daily_limit = manifest.get("daily_limit")
    if not isinstance(daily_limit, int) or not 1 <= daily_limit <= 3:
        raise PermanentError("daily_limit must be between 1 and 3")
    items = manifest.get("items")
    if not isinstance(items, list) or len(items) != 10:
        raise PermanentError("the reviewed pilot must contain exactly 10 items")

    unique_fields = {name: set() for name in ("publication_key", "slug")}
    tracking_keys: set[str] = set()
    schedules: list[datetime] = []
    scheduled_per_day: Counter[str] = Counter()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise PermanentError(f"item {index} is not an object")
        for field in ("publication_key", "slug", "category", "category_key", "symbol", "title", "description", "conclusion", "intro", "card_summary"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise PermanentError(f"item {index} is missing {field}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{8,80}", item["slug"]):
            raise PermanentError(f"invalid slug: {item['slug']}")
        if not re.fullmatch(r"coupang-direct-[a-z0-9-]{12,100}", item["publication_key"]):
            raise PermanentError(f"invalid publication_key: {item['publication_key']}")
        for field in unique_fields:
            if item[field] in unique_fields[field]:
                raise PermanentError(f"duplicate {field}: {item[field]}")
            unique_fields[field].add(item[field])
        schedule = parse_schedule(str(item.get("scheduled_at", "")))
        schedules.append(schedule)
        scheduled_per_day[schedule.date().isoformat()] += 1
        if scheduled_per_day[schedule.date().isoformat()] > daily_limit:
            raise PermanentError(f"schedule exceeds daily_limit on {schedule.date()}")
        hero_lines = item.get("hero_lines")
        sections = item.get("sections")
        if not isinstance(hero_lines, list) or len(hero_lines) != 2 or not all(isinstance(x, str) and x for x in hero_lines):
            raise PermanentError(f"item {index} requires two hero_lines")
        if not isinstance(sections, list) or len(sections) < 3:
            raise PermanentError(f"item {index} requires at least three sections")
        for section in sections:
            if not isinstance(section, dict) or not section.get("heading"):
                raise PermanentError(f"item {index} has an invalid section")
            if not isinstance(section.get("paragraphs"), list) or not section["paragraphs"]:
                raise PermanentError(f"item {index} section has no paragraphs")
            if not isinstance(section.get("bullets"), list) or len(section["bullets"]) < 3:
                raise PermanentError(f"item {index} section needs at least three bullets")
        product = item.get("product")
        if not isinstance(product, dict):
            raise PermanentError(f"item {index} product is missing")
        item_id = str(product.get("item_id", ""))
        affiliate_url = str(product.get("affiliate_url", ""))
        if item_id not in VERIFIED_LINKS or VERIFIED_LINKS[item_id] != affiliate_url:
            raise PermanentError(f"item {index} does not use the pre-verified item/link binding")
        parsed_url = urlparse(affiliate_url)
        if parsed_url.scheme != "https" or parsed_url.netloc != "link.coupang.com" or not re.fullmatch(r"/a/[A-Za-z0-9]+", parsed_url.path):
            raise PermanentError(f"item {index} has an invalid affiliate URL")
        tracking_key = str(product.get("tracking_key", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{8,100}", tracking_key):
            raise PermanentError(f"item {index} has an invalid tracking key")
        if tracking_key in tracking_keys:
            raise PermanentError(f"duplicate tracking key: {tracking_key}")
        tracking_keys.add(tracking_key)
        if product.get("checked_on") != "2026-09-14":
            raise PermanentError(f"item {index} lacks the reviewed link date")
        article_text = " ".join(iter_strings({k: item[k] for k in ("title", "description", "conclusion", "intro", "sections")}))
        if len(article_text) < 650:
            raise PermanentError(f"item {index} is too thin ({len(article_text)} characters)")
        if re.search(r"(?:최저가|무조건 구매|수익 보장|완치|치료된다|100% 효과)", article_text, re.I):
            raise PermanentError(f"item {index} contains a prohibited unsupported claim")
    if schedules != sorted(schedules):
        raise PermanentError("items must be ordered by scheduled_at")


def render_page(item: dict[str, Any], base_url: str) -> str:
    product = item["product"]
    canonical = base_url + "offers/" + item["slug"] + ".html"
    sections = []
    for section in item["sections"]:
        paragraphs = "".join(f"<p>{html.escape(text)}</p>" for text in section["paragraphs"])
        bullets = "".join(f"<li>{html.escape(text)}</li>" for text in section["bullets"])
        sections.append(f"<section><h2>{html.escape(section['heading'])}</h2>{paragraphs}<ul>{bullets}</ul></section>")
    document = f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <meta name="description" content="{html.escape(item['description'], quote=True)}" />
  <link rel="canonical" href="{html.escape(canonical, quote=True)}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{html.escape(item['title'], quote=True)}" />
  <title>{html.escape(item['title'])} | Atemoya</title>
  <link rel="stylesheet" href="../assets/story.css" />
  <script src="../config.js"></script>
  <script defer src="../assets/analytics.js"></script>
</head>
<body data-category="{html.escape(item['category_key'], quote=True)}">
  <header><div class="wrap nav"><a class="brand" href="../index.html">ATEMOYA</a><a href="index.html">구매 판단 가이드</a></div></header>
  <section class="storyhero"><div class="symbol">{html.escape(item['symbol'])}</div><div class="wrap heroCopy"><div class="category">{html.escape(item['category'])}</div><h1>{html.escape(item['hero_lines'][0])}<br />{html.escape(item['hero_lines'][1])}</h1><p class="dek">{html.escape(item['description'])}</p></div></section>
  <main class="article">
    <div class="answer"><b>먼저 결론</b><br />{html.escape(item['conclusion'])}</div>
    <p>{html.escape(item['intro'])}</p>
    {''.join(sections)}
    <div class="disclosure">{DISCLOSURE}</div>
    <div class="ctaBox"><h3>{html.escape(product['name'])}</h3><p>구성, 사용 안내, 배송·반품 조건은 판매 페이지에서 최신 정보를 다시 확인하세요.</p><a class="cta" data-affiliate data-link-key="{html.escape(product['tracking_key'], quote=True)}" href="{html.escape(product['affiliate_url'], quote=True)}" rel="sponsored nofollow">상품 정보 확인 →</a></div>
    <p class="sources">상품 ID {html.escape(product['item_id'])} · 링크 확인일 {html.escape(product['checked_on'])} · 가격과 재고는 변동될 수 있습니다.</p>
  </main>
</body>
</html>
'''
    validate_rendered(document, item, base_url)
    return document


def validate_rendered(document: str, item: dict[str, Any], base_url: str) -> None:
    product = item["product"]
    expected_canonical = base_url + "offers/" + item["slug"] + ".html"
    errors = []
    if document.count(DISCLOSURE) != 1:
        errors.append("exact Coupang disclosure must appear once")
    if document.count(product["affiliate_url"]) != 1:
        errors.append("affiliate URL must appear once")
    if f'data-link-key="{product["tracking_key"]}"' not in document:
        errors.append("tracking key missing")
    if 'rel="sponsored nofollow"' not in document:
        errors.append("sponsored nofollow missing")
    if f'<link rel="canonical" href="{expected_canonical}"' not in document:
        errors.append("canonical mismatch")
    if re.search(r"(?:TODO|TBD|PLACEHOLDER|javascript:|onerror\s*=|<iframe)", document, re.I):
        errors.append("placeholder or unsafe markup detected")
    visible = re.sub(r"<[^>]+>", " ", document)
    visible = re.sub(r"\s+", " ", visible).strip()
    if len(visible) < 850:
        errors.append(f"rendered article is too thin ({len(visible)} characters)")
    if errors:
        raise PermanentError(f"{item['publication_key']}: " + "; ".join(errors))


def render_hub_card(item: dict[str, Any]) -> str:
    return (
        f'    <a class="card" href="{html.escape(item["slug"], quote=True)}.html">'
        f'<div class="symbol">{html.escape(item["symbol"])}</div><div class="cardText">'
        f'<span>{html.escape(item["category"])}</span><b>{html.escape(item["title"])}</b>'
        f'<p>{html.escape(item["card_summary"])}</p></div></a>'
    )


def update_hub(document: str, item: dict[str, Any]) -> str:
    href = f'{item["slug"]}.html'
    replacements = {
        "뷰티, 주방, 생활가전, 운동, 반려동물, 육아, 여행, 사무, 계절가전, 전자기기 구매 전에 확인할 조건을 정리합니다.": "제품을 사기 전에 사용 환경, 유지관리, 안전과 반품 조건을 확인하는 실용 가이드입니다.",
        "카테고리별 구매 체크리스트 10선 | Atemoya": "구매 전 판단 가이드 | Atemoya",
        "사기 전에 확인할<br />10개 카테고리 체크리스트": "사기 전에 확인할<br />카테고리별 판단 가이드",
        "가격을 단정하지 않고 용도, 크기, 관리 조건과 반품 기준을 먼저 확인합니다.": "가격을 단정하지 않고 용도, 크기, 관리 조건과 반품 기준을 먼저 확인합니다. 새 글은 검증된 링크만 사용해 순차 공개합니다.",
    }
    for before, after in replacements.items():
        document = document.replace(before, after)
    if f'href="{href}"' in document:
        return document
    marker = "  </main>"
    if marker not in document:
        raise PermanentError("offers/index.html has no safe card insertion marker")
    return document.replace(marker, render_hub_card(item) + "\n" + marker, 1)


def manifest_item(manifest: dict[str, Any], publication_key: str) -> dict[str, Any]:
    for item in manifest["items"]:
        if item["publication_key"] == publication_key:
            return item
    raise PermanentError(f"database job is absent from reviewed manifest: {publication_key}")


def recover_expired_leases() -> None:
    db("""
      UPDATE affiliate.jobs j
      SET state=CASE WHEN attempt>=max_attempts THEN 'manual_review' ELSE 'retry_wait' END,
          next_attempt_at=CASE WHEN attempt>=max_attempts THEN next_attempt_at ELSE now()+interval '15 minutes' END,
          lease_owner=NULL,lease_expires_at=NULL,last_error='expired publisher lease recovered',updated_at=now()
      WHERE kind='direct_affiliate_publish' AND state='running' AND lease_expires_at<now();
      UPDATE affiliate.publications p SET state=CASE WHEN j.attempt>=j.max_attempts THEN 'manual_review' ELSE 'retry_wait' END
      FROM affiliate.jobs j WHERE p.idempotency_key=j.payload->>'publication_key'
        AND j.kind='direct_affiliate_publish' AND p.state='building' AND j.state IN ('retry_wait','manual_review');
    """)


def select_job(claim: bool) -> dict[str, Any] | None:
    daily_count = """(
      SELECT count(*) FROM affiliate.publications px
      WHERE px.authorization_mode='direct_user_instruction' AND px.state='published'
        AND timezone('Asia/Seoul',px.verified_at)::date=timezone('Asia/Seoul',now())::date
    )"""
    blocking = """NOT EXISTS (
      SELECT 1 FROM affiliate.jobs bx
      WHERE bx.kind='direct_affiliate_publish' AND bx.state IN ('manual_review','failed')
    ) AND NOT EXISTS (
      SELECT 1 FROM affiliate.jobs dx
      JOIN affiliate.publications dp ON dp.idempotency_key=dx.payload->>'publication_key'
      WHERE dx.kind='direct_affiliate_publish' AND dp.state='deploying'
    )"""
    if not claim:
        rows = db_json(f"""
          SELECT j.* FROM affiliate.jobs j JOIN affiliate.publications p ON p.idempotency_key=j.payload->>'publication_key'
          WHERE j.kind='direct_affiliate_publish' AND j.state IN ('queued','retry_wait')
            AND p.state IN ('queued','retry_wait') AND j.next_attempt_at<=now()
            AND {daily_count}<COALESCE((j.payload->>'daily_limit')::int,1) AND {blocking}
          ORDER BY j.next_attempt_at,j.id LIMIT 1
        """)
        return rows[0] if rows else None
    owner = f"{socket.gethostname()}:{os.getpid()}"
    row = db_row(f"""
      WITH candidate AS (
        SELECT j.id FROM affiliate.jobs j JOIN affiliate.publications p ON p.idempotency_key=j.payload->>'publication_key'
        WHERE j.kind='direct_affiliate_publish' AND j.state IN ('queued','retry_wait')
          AND p.state IN ('queued','retry_wait') AND j.next_attempt_at<=now()
          AND {daily_count}<COALESCE((j.payload->>'daily_limit')::int,1) AND {blocking}
        ORDER BY j.next_attempt_at,j.id FOR UPDATE OF j SKIP LOCKED LIMIT 1
      ), claimed AS (
        UPDATE affiliate.jobs j SET state='running',attempt=attempt+1,lease_owner={quote(owner)},
          lease_expires_at=now()+interval '12 minutes',fence_token=fence_token+1,last_error=NULL,updated_at=now()
        FROM candidate c WHERE j.id=c.id RETURNING j.*
      ), marked AS (
        UPDATE affiliate.publications p SET state='building' FROM claimed j
        WHERE p.idempotency_key=j.payload->>'publication_key' RETURNING p.id
      ) SELECT row_to_json(claimed) FROM claimed
    """)
    return row


def prepare_public_worktree() -> Path:
    if not PUBLIC_WORKTREE.exists():
        PUBLIC_WORKTREE.parent.mkdir(parents=True, exist_ok=True)
        require_command(["git", "fetch", "origin", "main"], cwd=ROOT, timeout=180)
        require_command(["git", "worktree", "add", "--detach", str(PUBLIC_WORKTREE), "origin/main"], cwd=ROOT, timeout=120)
    if not (PUBLIC_WORKTREE / ".git").exists():
        raise PermanentError(f"publication path is not a Git worktree: {PUBLIC_WORKTREE}")
    status = require_command(["git", "status", "--porcelain"], cwd=PUBLIC_WORKTREE)
    if status:
        raise PermanentError("publication worktree has unreviewed changes: " + status[:500])
    require_command(["git", "fetch", "origin", "main"], cwd=PUBLIC_WORKTREE, timeout=180)
    require_command(["git", "checkout", "--detach", "origin/main"], cwd=PUBLIC_WORKTREE)
    return PUBLIC_WORKTREE


def cleanup_generated_paths(worktree: Path, paths: list[str]) -> None:
    command(["git", "restore", "--staged", "--"] + paths, cwd=worktree)
    tracked = set(require_command(["git", "ls-files"], cwd=worktree).splitlines())
    for relative in paths:
        path = worktree / relative
        if relative in tracked:
            command(["git", "restore", "--worktree", "--", relative], cwd=worktree)
        elif path.is_file():
            path.unlink()


def run_release_checks(worktree: Path) -> None:
    node = node_binary()
    require_command([node, "scripts/build-sitemap.mjs"], cwd=worktree)
    require_command([node, "scripts/test-site.mjs"], cwd=worktree)
    affiliate_inventory_test = worktree / "scripts/test-affiliate-batch.mjs"
    if affiliate_inventory_test.is_file():
        require_command([node, "scripts/test-affiliate-batch.mjs"], cwd=worktree)
    output = worktree / "dist-public"
    if output.exists():
        if output.resolve().parent != worktree.resolve():
            raise PermanentError("refusing unexpected public output path")
        shutil.rmtree(output)
    require_command([node, "scripts/build-public.mjs"], cwd=worktree)
    require_command([node, "scripts/test-site.mjs", "dist-public"], cwd=worktree)
    require_command([node, "--test", "scripts/test-analytics.mjs", "scripts/test-public-package.mjs"], cwd=worktree)


def verify_public_page(item: dict[str, Any], base_url: str, timeout_seconds: int) -> bool:
    url = base_url + "offers/" + item["slug"] + ".html"
    expected_hash = sha256_text(render_page(item, base_url))
    deadline = time.monotonic() + max(1, timeout_seconds)
    while True:
        try:
            request = Request(url, headers={"User-Agent": "Atemoya-Publication-Verifier/1.0", "Cache-Control": "no-cache"})
            with urlopen(request, timeout=12) as response:
                body = response.read().decode("utf-8", "replace")
            normalized = normalize_deployed_html(body)
            if response.status == 200 and sha256_text(normalized) == expected_hash and item["product"]["affiliate_url"] in body and DISCLOSURE in body and item["title"] in body:
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(10, max(1, deadline - time.monotonic())))


def mark_success(job: dict[str, Any], item: dict[str, Any], commit: str, public_url: str) -> None:
    job_id = int(job["id"])
    key = item["publication_key"]
    db(f"""
      BEGIN;
      UPDATE affiliate.jobs SET state='succeeded',result_ref={quote(public_url)},lease_owner=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=now()
        WHERE id={job_id} AND fence_token={int(job['fence_token'])};
      UPDATE affiliate.publications SET state='published',git_commit={quote(commit)},public_url={quote(public_url)},verified_at=now()
        WHERE idempotency_key={quote(key)};
      UPDATE public.content SET status='published',published_url={quote(public_url)},published_at=COALESCE(published_at,now()),updated_at=now()
        WHERE external_key={quote(key)};
      INSERT INTO affiliate.outbox(event_key,kind,payload,state)
        VALUES({quote('published:' + key)},'direct_affiliate_published',jsonb_build_object('publication_key',{quote(key)},'url',{quote(public_url)},'git_commit',{quote(commit)}),'pending')
        ON CONFLICT(event_key) DO NOTHING;
      COMMIT;
    """)


def mark_pending(job: dict[str, Any], item: dict[str, Any], commit: str, public_url: str) -> None:
    db(f"""
      UPDATE affiliate.jobs SET state='retry_wait',next_attempt_at=now()+interval '15 minutes',lease_owner=NULL,lease_expires_at=NULL,
        result_ref={quote(public_url)},last_error='deployment pushed; waiting for public verification',updated_at=now()
      WHERE id={int(job['id'])} AND fence_token={int(job['fence_token'])};
      UPDATE affiliate.publications SET state='deploying',git_commit={quote(commit)},public_url={quote(public_url)}
      WHERE idempotency_key={quote(item['publication_key'])};
    """)


def mark_failure(job: dict[str, Any], item: dict[str, Any], exc: Exception) -> None:
    permanent = isinstance(exc, PermanentError) or int(job.get("attempt") or 0) >= int(job.get("max_attempts") or 3)
    state = "manual_review" if permanent else "retry_wait"
    publication_state = "manual_review" if permanent else "retry_wait"
    retry = "next_attempt_at" if permanent else "now()+interval '1 hour'"
    message = str(exc)[:1200]
    db(f"""
      UPDATE affiliate.jobs SET state={quote(state)},next_attempt_at={retry},lease_owner=NULL,lease_expires_at=NULL,
        last_error={quote(message)},updated_at=now() WHERE id={int(job['id'])} AND fence_token={int(job['fence_token'])};
      UPDATE affiliate.publications SET state={quote(publication_state)} WHERE idempotency_key={quote(item['publication_key'])};
    """)


def mark_unbound_failure(job: dict[str, Any], exc: Exception) -> None:
    """Fail closed when a claimed row cannot be mapped to the reviewed manifest."""
    message = str(exc)[:1200]
    db(f"""
      UPDATE affiliate.jobs SET state='manual_review',next_attempt_at=next_attempt_at,
        lease_owner=NULL,lease_expires_at=NULL,last_error={quote(message)},updated_at=now()
      WHERE id={int(job['id'])} AND fence_token={int(job['fence_token'])};
    """)


def reconcile_deployments(manifest: dict[str, Any]) -> list[str]:
    rows = db_json("""
      SELECT j.*,p.public_url,p.git_commit FROM affiliate.jobs j
      JOIN affiliate.publications p ON p.idempotency_key=j.payload->>'publication_key'
      WHERE j.kind='direct_affiliate_publish' AND j.state='retry_wait' AND p.state='deploying'
      ORDER BY j.id
    """)
    completed = []
    for row in rows:
        item = manifest_item(manifest, row["payload"]["publication_key"])
        if verify_public_page(item, manifest["base_url"], 1):
            row["fence_token"] = row.get("fence_token", 0)
            mark_success(row, item, str(row.get("git_commit") or ""), str(row["public_url"]))
            completed.append(item["publication_key"])
    return completed


def deploy_job(job: dict[str, Any], manifest: dict[str, Any], verify_timeout: int) -> dict[str, Any]:
    payload = job.get("payload")
    if not isinstance(payload, dict):
        raise PermanentError("job payload is not JSON")
    publication_key = str(payload.get("publication_key", ""))
    item = manifest_item(manifest, publication_key)
    if job.get("payload_hash") != item_digest(item):
        raise PermanentError("job payload hash differs from reviewed manifest")
    if payload.get("authorization_mode") != "direct_user_instruction":
        raise PermanentError("job authorization is not direct_user_instruction")
    expected_path = "offers/" + item["slug"] + ".html"
    if payload.get("public_path") != expected_path:
        raise PermanentError("job path differs from reviewed manifest")
    document = render_page(item, manifest["base_url"])
    artifact_hash = sha256_text(document)
    publication = db_json("SELECT artifact_hash,state FROM affiliate.publications WHERE idempotency_key=" + quote(publication_key))
    if len(publication) != 1 or publication[0]["artifact_hash"] != artifact_hash:
        raise PermanentError("rendered artifact hash differs from immutable publication binding")

    worktree = prepare_public_worktree()
    paths = [expected_path, "offers/index.html", "sitemap.xml"]
    try:
        target = worktree / expected_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
        hub = worktree / "offers/index.html"
        hub.write_text(update_hub(hub.read_text(encoding="utf-8"), item), encoding="utf-8")
        run_release_checks(worktree)
        require_command(["git", "add", "--"] + paths, cwd=worktree)
        staged = require_command(["git", "diff", "--cached", "--name-only"], cwd=worktree).splitlines()
        if set(staged) - set(paths):
            raise PermanentError("publication staging boundary was violated")
        tracked_page = command(["git", "ls-files", "--error-unmatch", expected_path], cwd=worktree).returncode == 0
        if expected_path not in staged and not tracked_page:
            raise PermanentError("publication page is neither staged nor already tracked")
        if staged:
            require_command(["git", "commit", "-m", "content(affiliate): publish " + item["slug"]], cwd=worktree)
            commit = require_command(["git", "rev-parse", "HEAD"], cwd=worktree)
            try:
                require_command(["git", "push", "origin", "HEAD:main"], cwd=worktree, timeout=180)
            except Exception:
                cleanup_generated_paths(worktree, paths)
                raise
        else:
            # A previous attempt may have pushed successfully and failed before
            # recording the DB transition. Reuse that exact public commit.
            commit = require_command(["git", "rev-parse", "HEAD"], cwd=worktree)
    except Exception:
        status = command(["git", "status", "--porcelain"], cwd=worktree)
        if status.returncode == 0 and status.stdout.strip():
            cleanup_generated_paths(worktree, paths)
        raise

    public_url = manifest["base_url"] + expected_path
    db(f"UPDATE affiliate.publications SET state='deploying',git_commit={quote(commit)},public_url={quote(public_url)} WHERE idempotency_key={quote(publication_key)};")
    if verify_public_page(item, manifest["base_url"], verify_timeout):
        mark_success(job, item, commit, public_url)
        return {"status": "published", "publication_key": publication_key, "url": public_url, "commit": commit}
    mark_pending(job, item, commit, public_url)
    raise DeploymentPending(f"deployment pushed and is awaiting public verification: {public_url}")


def validate_all(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = []
    for item in manifest["items"]:
        document = render_page(item, manifest["base_url"])
        artifacts.append({
            "publication_key": item["publication_key"],
            "scheduled_at": item["scheduled_at"],
            "public_path": "offers/" + item["slug"] + ".html",
            "artifact_hash": sha256_text(document),
            "visible_characters": len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", document)).strip()),
        })
    return {"status": "valid", "batch_key": manifest["batch_key"], "daily_limit": manifest["daily_limit"], "artifacts": artifacts}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--validate-all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-timeout", type=int, default=240)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.validate_all:
        print(json.dumps(validate_all(manifest), ensure_ascii=False, indent=2))
        return 0

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "skipped", "reason": "publisher lock active"}, ensure_ascii=False))
            return 0
        recover_expired_leases()
        reconciled = reconcile_deployments(manifest)
        if args.dry_run:
            job = select_job(False)
            result = {"status": "ready" if job else "idle", "reconciled": reconciled, "job": job}
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return 0
        job = select_job(True)
        if not job:
            print(json.dumps({"status": "idle", "reconciled": reconciled}, ensure_ascii=False))
            return 0
        item: dict[str, Any] | None = None
        try:
            payload = job.get("payload")
            if not isinstance(payload, dict):
                raise PermanentError("claimed job payload is not JSON")
            item = manifest_item(manifest, str(payload.get("publication_key", "")))
            result = deploy_job(job, manifest, max(1, args.verify_timeout))
            result["reconciled"] = reconciled
            print(json.dumps(result, ensure_ascii=False))
            return 0
        except DeploymentPending as exc:
            assert item is not None
            print(json.dumps({"status": "deploying", "publication_key": item["publication_key"], "message": str(exc)}, ensure_ascii=False))
            return 0
        except Exception as exc:
            if item is None:
                mark_unbound_failure(job, exc)
                publication_key = str(job.get("job_key") or "unknown")
            else:
                mark_failure(job, item, exc)
                publication_key = item["publication_key"]
            print(json.dumps({"status": "failed", "publication_key": publication_key, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
