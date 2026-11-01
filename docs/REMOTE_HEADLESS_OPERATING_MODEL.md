# Atemoya remote headless operating model

> 2026-11-01 적용 상태와 인수 결과는 [운영 구조와 검증 기록](OPERATING_MAP_2026-11-01.md)을 우선한다. 아래는 설계 당시의 목표와 이전 상태를 보존한 문서다.

## 2026-11-02 실제 경계와 복구 방향

| 상태 | 현재 구조 | 운영 판단 |
| --- | --- | --- |
| 화면만 잠김 | 로그인한 사용자 세션은 유지된다. n8n·PostgreSQL 컨테이너, Watchdog, 대시보드 API, Ollama는 화면 입력 없이 동작한다. | `scripts/preflight.sh`, Docker/launchctl, HTTP, PostgreSQL로 점검한다. 잠금 해제를 요청하지 않는다. |
| 사용자 로그아웃·재부팅 후 로그인 전 | 핵심 예약 작업은 `~/Library/LaunchAgents`의 사용자 세션에 있다. `com.atemoya.start-services`도 로그인 뒤 Docker Desktop을 여는 LaunchAgent다. Docker 컨테이너의 `restart: unless-stopped`는 Docker Desktop 자체를 시작하지 않는다. | 자동 복구가 보장되지 않는다. 재부팅·로그아웃은 화면 잠금과 별도 장애 경계로 감시한다. |
| Chrome 웹 편집 | 잠긴 상태에서도 Chrome 원격 탭은 접근됐다. 현재 네이버 탭은 작성자 비로그인 상태다. | 웹 편집은 실제 탭 접근성을 먼저 확인한다. 네이버는 작성자 인증 뒤 편집하며, 화면 잠금만으로 막혔다고 판단하지 않는다. |
| 네이티브 앱 GUI | macOS 화면 잠금 중 네이티브 앱 제어는 접근 불가로 확인됐다. | 해당 GUI 시험이 필요한 순간에만 잠금 해제를 요청한다. |

2026-11-02 실측: macOS 네이티브 GUI가 잠겼다고 확인된 바로 그 상태에서 Chrome 원격 탭은 접근됐고 n8n `/healthz`가 `{"status":"ok"}`, PostgreSQL `pg_isready`가 연결 수락, 대시보드 API가 `n8n.ok=true`로 응답했다. 세 컨테이너가 실행 중이고 Watchdog LaunchAgent는 예약 등록·최근 정상 종료 상태였다. iMac은 전원 연결 시 시스템 수면이 꺼져 있다. Telegram의 잠금 중 휴대폰 왕복과 재부팅 후 로그인 전 복구는 아직 시험하지 않았다.

**단기 운영:** Telegram과 원격 Codex의 상태·진단·재시작은 기존 API/CLI 경로만 사용한다. GUI 실패를 서버 장애로 분류하지 않는다. 외부 네이버 글의 로그인·편집은 별도 미결 작업으로 남긴다. 잠금 상태에서 휴대폰 Telegram `상태` 명령의 실제 왕복을 추가 확인한다.

**상시 서버로 전환할 때:** 사용자 로그인 전에도 필요한 PostgreSQL·n8n·모니터링을 시스템 서비스로 기동할 수 있는 Linux VM 또는 별도 Linux 호스트로 옮기고, Tailscale과 외부 heartbeat를 별도로 검증한다. 기존 Mac LaunchAgent만 LaunchDaemon으로 바꿔도 Docker Desktop의 로그인 의존성은 사라지지 않는다. 백업·복원·재부팅 시험 후 단계적으로 이전한다. 현재 이 전환은 설계이며 배포 완료 상태가 아니다.

아래는 이전 설계 참고자료다. 현재 사업 범위와 활성 워크플로는 `ops/business-scope-20261101.json`과 실제 상태가 우선한다.

Purpose: reduce repeated Mac unlock requests by moving Atemoya operations away
from browser and desktop UI control. The iMac should run like a small server.

## Principle

The Mac screen lock must not stop normal Atemoya operation.

Screen unlock is required only for account authentication, 2FA, payment,
browser-only login sessions, and one-time permission prompts. Everything else
must be runnable through CLI, local HTTP APIs, n8n webhooks, PostgreSQL, Git,
and LaunchAgents.

## Operating layers

1. Runtime layer
   - Docker containers: PostgreSQL, n8n, webhook proxy.
   - LaunchAgents: watchdog, source scout, local LLM, status dashboard,
     revenue reconciler, autopilot publisher.
   - Requirement: these keep running while macOS is locked.

2. Control layer
   - n8n webhooks for safe operational actions.
   - Local dashboard API for status.
   - PostgreSQL for state, queues, approvals, incidents and run history.
   - Git for workflow exports, scripts, docs and public site artifacts.

3. Conversation layer
   - Telegram remains the owner interface.
   - Explicit slash commands remain supported for recovery.
   - Natural language is routed through local Ollama first and then validated by
     deterministic rules before any state change.
   - Ambiguous commands ask one question. Clear low-risk commands proceed.

4. Human-only layer
   - Google, Naver, Coupang, Blogger, Search Console, OAuth, 2FA, payment and
     legal consent stay manual.
   - After the user completes the human-only step, the automation records and
     verifies the resulting state without needing further screen control.

## Required interfaces

### n8n

- Keep active production workflows exported under `n8n/workflows/exports/`.
- Apply known workflow exports through CLI/API instead of browser import.
- Production workflow changes must preserve credential references and must not
  export secret values.
- AI-provider calls must have local fallback where a useful local result is
  acceptable.

### PostgreSQL

The DB remains the source for operational state. The following views or queries
should power Telegram and dashboard responses:

- latest workflow failures by workflow, execution id, node and error.
- local LLM queue status, including stale running and queued jobs.
- pending approvals with latest single pending item.
- recent publications and public URLs.
- source freshness and latest evidence URLs.
- system incidents with open/resolved status.

### Telegram

Telegram should support natural language forms such as:

- "오늘 상태 어때"
- "오류 원인 알려줘"
- "최근 게시 링크 보여줘"
- "방금 승인 요청 게시해"
- "이건 보류"
- "수익 후보 다시 찾아"

The LLM may classify intent and draft the answer, but it may not be the sole
authority for a state-changing action. State changes require deterministic
validation such as an approval id, exactly one pending approval, or a known
safe action.

The natural-language DB path is backed by read-only operational views and the
whitelist table `telegram_safe_query_catalog`. Ollama `qwen3.5:4b` classifies
and summarizes; it does not generate arbitrary SQL. Audit rows are stored in
`telegram_natural_language_queries`. Details live in
`ops/TELEGRAM_NATURAL_LANGUAGE_DB.md`.

### Local dashboard

The dashboard should expose:

- service health: n8n, PostgreSQL, Ollama, Docker containers.
- local jobs: running, queued, completed, failed, stale.
- memory and disk pressure.
- scheduled jobs with last run, next expected run and stale threshold.
- recent n8n failures with node names.
- latest published URLs and measurement status.

Dashboard status must come from `/api/status`; static HTML must never be called
"working" unless the API is reachable.

## Unlock policy

Do not request Mac unlock for:

- checking status.
- reading DB state.
- running local scripts.
- applying migrations through approved scripts.
- importing n8n workflows through CLI/API.
- restarting existing containers within watchdog limits.
- generating drafts, local LLM runs, reports, or site files.

Request Mac unlock only for:

- browser-only account login.
- OAuth consent screens.
- 2FA, password, recovery code or security prompt.
- visual inspection of a page that cannot be checked by HTTP/API.
- manual public post submission when no approved API exists.

## Failure handling

If a cloud AI node returns service unavailable:

1. Retry with backoff.
2. Use local Ollama fallback if the task allows local quality.
3. Store provider, model, fallback status and error summary.
4. Telegram reports the fallback result, not only the raw error.
5. Open an incident only if both cloud and local fallback fail, or if the same
   component keeps failing past the incident threshold.

## Next implementation steps

1. Keep `scripts/preflight.sh` as the skill-compatible entry point.
2. Add or maintain a local n8n workflow apply path using the n8n CLI on the
   iMac.
3. Keep `AtemoyaDailyTrend01` on Gemini retry plus Ollama fallback.
4. Keep `AtemoyaTelegramMemory01` on natural-language owner routing.
5. Extend the dashboard API with latest n8n failure node and next scheduled
   run details.
6. Record the unlock policy in the baseline and open items.
