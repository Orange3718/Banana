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
