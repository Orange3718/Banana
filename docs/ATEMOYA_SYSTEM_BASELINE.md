# Atemoya system baseline

Verified: 2026-08-13 (Asia/Seoul)

## Authority and roles

- **Atemoya** is the project, brand and AI-operated portfolio system.
- **GitHub `Orange3718/Banana`** is the source of truth for code, schema,
  workflow exports and operating documentation.
- **iMac `orange-imac`** is the current automation server.
- **PostgreSQL 16** is operational memory; **n8n** is orchestration.
- **Telegram** is immediate alert/approval transport. Existing credentials and
  the inactive `Telegram 연결 테스트` workflow must be preserved.
- **Gmail** is the formal reporting channel; **Google Calendar** carries the
  management routine; **Obsidian** is the last-stage human-readable second brain.
- The first operating workflow is **Business Scout**. The first revenue asset is
  **AI Hardware Lab** at `https://orange3718.github.io/Banana/`.

## Verified runtime

- Running: `atemoya-postgres` (`postgres:16-alpine`) and `atemoya-n8n`
  (`n8nio/n8n:latest`) on `atemoya-net` with named persistent volumes and
  `unless-stopped` restart policy.
- Running separately: `atemoya-webhook-proxy` (`nginx:1.27-alpine`) on the
  default bridge network. Its current bind-mounted configuration is not yet in
  Git and is deliberately not replaced by this baseline.
- n8n responds on local port 5678 and PostgreSQL accepts connections.
- Tailscale reports `orange-imac` online. The device named `orange` is Android,
  not a duplicate iMac. The Windows device was offline at the time of audit.
- The remote setup record remains in
  `notes/REMOTE_N8N_SETUP_2026-08-12.md`.

## Repository state found during audit

- Remote `main` and the original iMac `main` had diverged: the iMac contained
  four Hardware Lab/commerce commits while remote `main` had twelve newer
  commits.
- The four local commits and unrelated uncommitted files are preserved on
  `backup/local-hardware-lab-20260813` in the original worktree.
- This baseline is isolated on `feat/atemoya-ops-baseline`, based on current
  `origin/main`.
- `origin/feat/automated-content-quality` contains five quality/SEO commits
  based on the older common commit. It must not be merged blindly because both
  it and current `main` remove or rewrite many of the same site files.

## Recovery order

1. Confirm iMac, Tailscale and Docker Desktop are online.
2. Run `./ops/scripts/backup.sh` and retain the printed backup path.
3. Confirm `atemoya-postgres` and `atemoya-n8n` use the named volumes.
4. Apply additive migrations with `./ops/scripts/apply-migrations.sh`.
5. Run `./ops/scripts/verify.sh`.
6. Import workflow JSON inactive, map existing credential references, review,
   then activate only with Owner approval.
7. For failure, leave volumes intact and follow `ops/BACKUP_RESTORE.md`.

## Business Scout baseline

The checked-in skeleton performs Schedule → public RSS collection → in-run
deduplication → AI evaluation placeholder → PostgreSQL upsert → Telegram
summary. Collection and database nodes retry three times. A separate error
workflow records failure in `executions` and alerts Telegram. External AI API
keys are intentionally absent; the workflow remains inactive by default.

## Known issues and next phase

1. Pin n8n to a tested immutable version after a restore drill; `latest` is not
   reproducible.
2. Reconcile the Hardware Lab commits with current remote `main` via a focused
   PR or selective cherry-picks, not a direct merge of the divergent local main.
3. Port the useful quality-gate commits onto a fresh branch from current main,
   resolve the Pages workflow intentionally, and open a separate PR.
4. Export and review the live workflows into `n8n/workflows/exports/` without
   credentials.
5. Add an approved AI provider credential, configure the existing PostgreSQL
   and Telegram credential references, dry-run Business Scout, then activate.
6. Bring the webhook proxy configuration under version control only after its
   routing and TLS/Funnel behavior are documented and a rollback is prepared.
7. Connect Gmail reporting, Calendar routines and finally Obsidian after the
   core workflow produces verified operational records.

## Obsidian Inbox bridge

The first human-readable bridge is `ops/scripts/export-obsidian-inbox.sh`.
It writes a single Markdown dashboard to `~/AtemoyaVault/00 Inbox` from
the nine operational-memory tables. It includes only new/evaluating ideas,
pending approvals and recent failed/retrying executions. PostgreSQL remains the
source of truth, and no credential or secret fields are exported.
The iMac LaunchAgent `com.atemoya.obsidian-inbox` refreshes this dashboard
every 15 minutes and once at login. Its configuration is local because the
absolute Vault and worktree paths are machine-specific.

## AI provider routing

- Google Gemini `gemini-2.5-flash` replaced the direct Ollama HTTP calls in the
  daily trend, 12-week commerce scout and Telegram memory workflows.
- The Gemini credential is encrypted in n8n and its API test returned HTTP 200.
- An xAI credential is encrypted in n8n as a future Grok fallback. The xAI
  models endpoint currently returns HTTP 403, so Grok is not in the live route.
- No provider key is stored in Git, workflow JSON, documentation or Obsidian.
- The pre-change workflow exports are retained outside Git under the private
  Atemoya backup directory; current secret-free exports live in
  `n8n/workflows/exports/`.

## AI Hardware Lab execution orchestrator

`AtemoyaHardwareExecution01` advances one approval-free AI Hardware Lab task
at a time from `business_unit_tasks`. It records the run in `executions` and
`agent_actions`, generates an internal specification draft, stores it in
`content` with `review_ready` status, and reports the result to Telegram.

The production route uses the iMac-local Ollama `qwen3.5:4b` model so a cloud
AI outage does not stop approved internal drafting. It never publishes,
purchases, logs in, or spends money. A run left in `running` for over fifteen
minutes is failed and its task is returned to `ready` on the next trigger.

## Operations Guardian

`com.atemoya.ops-watchdog` runs outside n8n every 15 minutes. It checks the
three containers, n8n, PostgreSQL, Ollama, source freshness, local-job
freshness, recent n8n errors, disk space and current macOS memory pressure.
It may only start an existing stopped container, restart an unresponsive n8n
container once per hour, kick a stale source collector, or mark expired local
jobs as failed. It cannot publish, spend, delete data, change credentials or
apply migrations.

The active n8n workflow `AtemoyaOpsGuardian01` runs at 03:10 KST. PostgreSQL
rules determine `GOOD`, `REVIEW` or `BAD`; local Ollama `qwen3.5:4b` only turns
those facts into a short report. Daily reviews are stored in
`ops_daily_reviews`. Incidents are stored in `system_incidents`, and Telegram
receives only a new incident, its resolution, and one daily report. The former
03:00 `com.atemoya.nightly-reflection` job is retained in Git for recovery but
must remain unloaded to prevent duplicate summaries.

## Revenue Autopilot

`AtemoyaRevenueAutopilot01` runs every 30 minutes. It promotes fresh,
evidence-backed `local_llm_runs` into a local-Qwen long-form draft, performs
deterministic QA, stores the result in PostgreSQL, and sends at most one active
Telegram publication approval request. No external model API is required.

`com.atemoya.autopilot-publisher` checks approved requests every 15 minutes,
renders safe HTML, rebuilds the sitemap, runs the site test, and commits only
the generated artifacts to `feat/atemoya-ops-baseline`. It never writes or
merges `main`. After a human PR merge, it detects the public Pages URL and
records the final publication. Queue state is held in
`revenue_autopilot_jobs`; details are in `ops/REVENUE_AUTOPILOT.md`.
