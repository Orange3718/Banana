# Telegram natural-language DB operations

Verified: 2026-09-07 (Asia/Seoul)

## Purpose

Telegram is the owner interface for Atemoya operations. The owner can ask
ordinary Korean questions instead of memorizing slash commands.

Examples:

- `오늘 상태 어때`
- `최근 오류 원인 알려줘`
- `승인 대기 있어?`
- `최근 게시 링크 보여줘`
- `수익 성과 어때`
- `수집 근거 뭐 있어?`

## Safety model

- Ollama `qwen3.5:4b` classifies the question and drafts the Korean response.
- The model never writes arbitrary SQL.
- DB reads are restricted to the approved views in
  `telegram_safe_query_catalog`.
- State-changing actions still pass deterministic validation in
  `AtemoyaTelegramMemory01`.
- Approval, defer and reject operations require either an explicit decision id
  or exactly one pending approval.
- Secrets, tokens, API keys, private keys and 2FA codes must never be written
  to Telegram, Git, Obsidian or logs.

## DB surface

Migration `012_telegram_natural_db_queries.sql` adds:

- `telegram_natural_language_queries`: audit log for natural-language DB
  questions and responses.
- `telegram_safe_query_catalog`: whitelist of allowed operational query keys.
- `v_atemoya_operational_status`: whole-system summary.
- `v_atemoya_recent_failures`: recent n8n errors.
- `v_atemoya_pending_approvals`: approval queue.
- `v_atemoya_recent_publications`: published content URLs.
- `v_atemoya_local_llm_status`: local model runs.
- `v_atemoya_source_freshness`: source collection evidence.
- `v_atemoya_recent_incidents`: open and recent incidents.
- `v_atemoya_revenue_status`: Revenue Autopilot and channel metrics summary.

## Local test tool

`tools/telegram-natural-db-query.py` provides a CLI equivalent of the Telegram
DB question path. It uses the same local model and the same safe query keys.

Examples:

```sh
tools/telegram-natural-db-query.py "오늘 상태 어때"
tools/telegram-natural-db-query.py "최근 오류 원인 알려줘"
tools/telegram-natural-db-query.py "수익 성과 어때"
```

## Deployment

1. Run `./ops/scripts/backup.sh`.
2. Run `./ops/scripts/apply-migrations.sh`.
3. Run `python3 tools/add-telegram-natural-language.py`.
4. Apply `AtemoyaTelegramMemory01.json` with
   `./ops/scripts/apply-n8n-workflows.sh AtemoyaTelegramMemory01.json`.
5. Run `./ops/scripts/verify.sh`.
6. Run local CLI questions and confirm they write to
   `telegram_natural_language_queries`.
