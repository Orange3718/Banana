# Atemoya remote headless operating model

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

